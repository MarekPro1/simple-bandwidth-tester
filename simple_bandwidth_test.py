#!/usr/bin/env python3
"""
Simple Bandwidth Test Tool
Only measures bandwidth between computers via SSH
"""

import paramiko
import json
import time
import sys

# SSH Credentials - DO NOT HARDCODE IN PRODUCTION
import os
USERNAME = os.getenv('SSH_USERNAME', 'admin')
PASSWORD = os.getenv('SSH_PASSWORD', '')  # Must be set as environment variable

class SimpleBandwidthTester:
    def __init__(self, config_file="network_config.json"):
        self.config_file = config_file
        self.computers = []
        self.load_config()
        
    def load_config(self):
        """Load only computers from config"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                # Only load computers, ignore switches for now
                self.computers = [d for d in config['devices'] if d['type'] == 'computer']
                print(f"Found {len(self.computers)} computers to test")
                for comp in self.computers:
                    print(f"  - {comp['name']} ({comp['ip']})")
        except Exception as e:
            print(f"Error loading config: {e}")
            sys.exit(1)
            
    def ssh_connect(self, ip):
        """Create SSH connection"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(ip, username=USERNAME, password=PASSWORD, timeout=10)
            return ssh
        except Exception as e:
            print(f"  Failed to connect to {ip}: {e}")
            return None
            
    def start_iperf_server(self, server_ip, server_name):
        """Start iperf3 server on a computer"""
        print(f"\nStarting iperf3 server on {server_name} ({server_ip})...")
        
        ssh = self.ssh_connect(server_ip)
        if not ssh:
            return False
            
        try:
            # Kill any existing iperf3 processes
            ssh.exec_command("taskkill /F /IM iperf3.exe 2>nul")
            time.sleep(1)
            
            # Use the correct iperf3 location (in subdirectory)
            iperf_path = r'C:\iperf3\iperf3.19.1_64\iperf3.exe'
            
            # Verify it exists
            stdin, stdout, stderr = ssh.exec_command(f'if exist "{iperf_path}" echo FOUND')
            if "FOUND" not in stdout.read().decode():
                print(f"  ERROR: iperf3 not found on {server_name}")
                print(f"  Please install iperf3 on {server_name} first")
                ssh.close()
                return False
                
            # Start iperf3 server in background using PowerShell
            ps_cmd = f'powershell -Command "Start-Process -FilePath \\"{iperf_path}\\" -ArgumentList \\"-s -p 5201\\" -WindowStyle Hidden"'
            ssh.exec_command(ps_cmd)
            time.sleep(3)
            
            # Verify server is running
            stdin, stdout, stderr = ssh.exec_command('netstat -an | findstr :5201')
            if "5201" in stdout.read().decode():
                print(f"  iperf3 server started successfully on {server_name}")
                ssh.close()
                return True
            else:
                print(f"  Failed to start iperf3 server on {server_name}")
                ssh.close()
                return False
                
        except Exception as e:
            print(f"  Error: {e}")
            ssh.close()
            return False
            
    def run_iperf_client(self, client_ip, client_name, server_ip, server_name):
        """Run iperf3 client test from one computer to another"""
        print(f"Running bandwidth test: {client_name} -> {server_name}...")
        
        ssh = self.ssh_connect(client_ip)
        if not ssh:
            return None
            
        try:
            # Use the correct iperf3 location (in subdirectory)
            iperf_path = r'C:\iperf3\iperf3.19.1_64\iperf3.exe'
            
            # Verify it exists
            stdin, stdout, stderr = ssh.exec_command(f'if exist "{iperf_path}" echo FOUND')
            if "FOUND" not in stdout.read().decode():
                print(f"  ERROR: iperf3 not found on {client_name}")
                ssh.close()
                return None
                
            # Run iperf3 client test
            cmd = f'"{iperf_path}" -c {server_ip} -t 10 -f m'  # 10 second test, output in Mbps
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=20)
            
            output = stdout.read().decode()
            errors = stderr.read().decode()
            
            if "Connection refused" in errors or "Connection refused" in output:
                print(f"  ERROR: Cannot connect to iperf3 server on {server_name}")
                ssh.close()
                return None
                
            # Parse bandwidth from output
            # Look for lines like: "[  4]   0.00-10.00  sec  1.09 GBytes   938 Mbits/sec"
            bandwidth_mbps = None
            lines = output.split('\n')
            for line in lines:
                if 'sender' in line.lower() or 'receiver' in line.lower():
                    continue  # Skip summary lines
                if 'bits/sec' in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if 'bits/sec' in part:
                            # Previous part should be the number
                            if i > 0:
                                value = parts[i-1]
                                try:
                                    bandwidth_mbps = float(value)
                                    # Check if it's in Gbits/sec
                                    if 'Gbits/sec' in part:
                                        bandwidth_mbps *= 1000
                                    elif 'Kbits/sec' in part:
                                        bandwidth_mbps /= 1000
                                    break
                                except:
                                    pass
                                    
            ssh.close()
            
            if bandwidth_mbps:
                print(f"  Result: {bandwidth_mbps:.2f} Mbps")
                return bandwidth_mbps
            else:
                print(f"  ERROR: Could not parse bandwidth from output")
                return None
                
        except Exception as e:
            print(f"  Error: {e}")
            ssh.close()
            return None
            
    def test_computer_pair(self, comp1, comp2):
        """Test bandwidth between two computers"""
        print(f"\n{'='*60}")
        print(f"Testing: {comp1['name']} <-> {comp2['name']}")
        print(f"{'='*60}")
        
        results = {}
        
        # Test comp1 -> comp2
        if self.start_iperf_server(comp2['ip'], comp2['name']):
            time.sleep(2)
            bandwidth = self.run_iperf_client(comp1['ip'], comp1['name'], 
                                             comp2['ip'], comp2['name'])
            if bandwidth:
                results[f"{comp1['name']}->{comp2['name']}"] = bandwidth
        
        # Test comp2 -> comp1 (reverse direction)
        if self.start_iperf_server(comp1['ip'], comp1['name']):
            time.sleep(2)
            bandwidth = self.run_iperf_client(comp2['ip'], comp2['name'],
                                             comp1['ip'], comp1['name'])
            if bandwidth:
                results[f"{comp2['name']}->{comp1['name']}"] = bandwidth
                
        return results
        
    def run_all_tests(self):
        """Test bandwidth between all computer pairs"""
        if len(self.computers) < 2:
            print("Need at least 2 computers to run bandwidth tests")
            return
            
        print("\n" + "="*60)
        print("SIMPLE BANDWIDTH TEST")
        print("="*60)
        
        all_results = {}
        
        # Test each pair of computers
        for i in range(len(self.computers)):
            for j in range(i+1, len(self.computers)):
                results = self.test_computer_pair(self.computers[i], self.computers[j])
                all_results.update(results)
                
        # Display final results
        print("\n" + "="*60)
        print("BANDWIDTH TEST RESULTS")
        print("="*60)
        
        if all_results:
            for connection, bandwidth in all_results.items():
                # Check if bandwidth meets expectations based on link speed
                status = "[OK]" if bandwidth > 100 else "[FAIL]"
                print(f"{connection:30} : {bandwidth:8.2f} Mbps {status}")
        else:
            print("No successful tests completed")
            
        print("="*60)

def main():
    if not PASSWORD:
        print("ERROR: SSH_PASSWORD environment variable not set!")
        print("Please set it using: set SSH_PASSWORD=your_password")
        sys.exit(1)
    tester = SimpleBandwidthTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()