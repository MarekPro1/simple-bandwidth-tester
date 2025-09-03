#!/usr/bin/env python3
"""
Advanced Network Monitoring Tool
Uses iperf3 with advanced parameters for detailed network performance analysis
"""

import paramiko
import json
import time
import sys
import argparse
import os
from datetime import datetime
import statistics

# Color codes for Windows terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    
# Enable colors on Windows
if sys.platform == 'win32':
    os.system('color')

class AdvancedNetworkMonitor:
    def __init__(self, username, password, config_file="network_config.json", verbose=False):
        self.username = username
        self.password = password
        self.config_file = config_file
        self.verbose = verbose
        self.computers = []
        self.load_config()
        
    def load_config(self):
        """Load only computers from config"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                # Only load computers, ignore switches for now
                self.computers = [d for d in config['devices'] if d['type'] == 'computer']
                print(f"\n{Colors.CYAN}{'='*80}")
                print(f"  ADVANCED NETWORK MONITOR")
                print(f"{'='*80}{Colors.END}")
                print(f"{Colors.WHITE}Found {Colors.BOLD}{len(self.computers)}{Colors.END} {Colors.WHITE}computers to test:{Colors.END}\n")
                for comp in self.computers:
                    link_speed = comp.get('link_speed', 'Unknown')
                    location = comp.get('location', 'Unknown')
                    print(f"  {Colors.GREEN}>{Colors.END} {Colors.BOLD}{comp['name']:<15}{Colors.END} {Colors.GRAY}({comp['ip']:<15}){Colors.END} - {Colors.CYAN}{link_speed:<7}{Colors.END} @ {Colors.YELLOW}{location}{Colors.END}")
        except Exception as e:
            print(f"{Colors.RED}Error loading config: {e}{Colors.END}")
            sys.exit(1)
            
    def ssh_connect(self, ip):
        """Create SSH connection"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            if self.verbose:
                print(f"  {Colors.GRAY}[DEBUG] Connecting to {ip}...{Colors.END}")
            ssh.connect(ip, username=self.username, password=self.password, timeout=10)
            if self.verbose:
                print(f"  {Colors.GREEN}[DEBUG] Connected successfully{Colors.END}")
            return ssh
        except Exception as e:
            if self.verbose:
                print(f"  {Colors.RED}[DEBUG] Failed to connect to {ip}: {e}{Colors.END}")
            return None
            
    def verify_iperf_server(self, server_ip):
        """Verify that iperf3 server is running"""
        ssh = self.ssh_connect(server_ip)
        if not ssh:
            return False
            
        try:
            stdin, stdout, stderr = ssh.exec_command('netstat -an | findstr :5201')
            netstat_output = stdout.read().decode()
            ssh.close()
            
            is_listening = "5201" in netstat_output and "LISTENING" in netstat_output
            
            if self.verbose:
                if is_listening:
                    print(f"  {Colors.GREEN}[DEBUG] Server ready on {server_ip}{Colors.END}")
                else:
                    print(f"  {Colors.RED}[DEBUG] Server NOT running on {server_ip}{Colors.END}")
            
            return is_listening
                
        except Exception as e:
            ssh.close()
            return False
    
    def run_advanced_test(self, client_ip, client_name, server_ip, server_name, test_params):
        """Run advanced iperf3 test with specified parameters"""
        ssh = self.ssh_connect(client_ip)
        if not ssh:
            return None
            
        try:
            iperf_path = r'C:\iperf3\iperf3.19.1_64\iperf3.exe'
            
            # Build iperf3 command with advanced parameters
            cmd_parts = [f'"{iperf_path}"', f'-c {server_ip}']
            
            # Add test parameters
            cmd_parts.append(f'-t {test_params.get("duration", 10)}')  # Test duration
            cmd_parts.append('-J')  # JSON output for detailed parsing
            
            # Add optional parameters
            if test_params.get('parallel'):
                cmd_parts.append(f'-P {test_params["parallel"]}')  # Parallel streams
                
            if test_params.get('udp'):
                cmd_parts.append('-u')  # UDP test for jitter/loss
                cmd_parts.append(f'-b {test_params.get("bandwidth", "100M")}')  # Target bandwidth for UDP
                
            if test_params.get('reverse'):
                cmd_parts.append('-R')  # Reverse test (server sends)
                
            if test_params.get('window'):
                cmd_parts.append(f'-w {test_params["window"]}')  # TCP window size
                
            if test_params.get('mss'):
                cmd_parts.append(f'-M {test_params["mss"]}')  # Maximum segment size
            
            cmd = ' '.join(cmd_parts)
            
            if self.verbose:
                print(f"  {Colors.GRAY}[DEBUG] Running: {cmd}{Colors.END}")
            
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=test_params.get('duration', 10) + 10)
            
            output = stdout.read().decode()
            errors = stderr.read().decode()
            
            if "Connection refused" in errors or "Connection refused" in output:
                print(f"  {Colors.RED}Cannot connect to server{Colors.END}")
                ssh.close()
                return None
            
            ssh.close()
            
            # Parse JSON output
            try:
                results = json.loads(output)
                return self.parse_iperf_results(results, test_params)
            except json.JSONDecodeError:
                if self.verbose:
                    print(f"  {Colors.RED}[DEBUG] Failed to parse JSON output{Colors.END}")
                return None
                
        except Exception as e:
            if self.verbose:
                print(f"  {Colors.RED}[DEBUG] Test error: {e}{Colors.END}")
            ssh.close()
            return None
    
    def parse_iperf_results(self, json_data, test_params):
        """Parse iperf3 JSON output for detailed metrics"""
        results = {
            'bandwidth': 0,
            'jitter': None,
            'packet_loss': None,
            'cpu_usage': None,
            'retransmits': None,
            'rtt': None
        }
        
        try:
            end_data = json_data.get('end', {})
            
            if test_params.get('udp'):
                # UDP test results
                streams = end_data.get('sum', {})
                results['bandwidth'] = streams.get('bits_per_second', 0) / 1000000  # Convert to Mbps
                results['jitter'] = streams.get('jitter_ms', 0)
                results['packet_loss'] = streams.get('lost_percent', 0)
            else:
                # TCP test results
                sum_sent = end_data.get('sum_sent', {})
                sum_received = end_data.get('sum_received', {})
                
                # Get bandwidth (prefer receiver side for accuracy)
                if sum_received:
                    results['bandwidth'] = sum_received.get('bits_per_second', 0) / 1000000
                elif sum_sent:
                    results['bandwidth'] = sum_sent.get('bits_per_second', 0) / 1000000
                
                # Get retransmits (TCP only)
                if sum_sent:
                    results['retransmits'] = sum_sent.get('retransmits', 0)
                
                # Get CPU usage
                cpu_data = end_data.get('cpu_utilization_percent', {})
                if cpu_data:
                    results['cpu_usage'] = {
                        'local': cpu_data.get('host_total', 0),
                        'remote': cpu_data.get('remote_total', 0)
                    }
                
                # Try to get RTT from streams
                streams = end_data.get('streams', [])
                if streams and len(streams) > 0:
                    sender = streams[0].get('sender', {})
                    if 'mean_rtt' in sender:
                        results['rtt'] = sender.get('mean_rtt', 0) / 1000  # Convert to ms
                        
        except Exception as e:
            if self.verbose:
                print(f"  {Colors.RED}[DEBUG] Parse error: {e}{Colors.END}")
        
        return results
    
    def run_comprehensive_test(self, comp1, comp2):
        """Run multiple test types between two computers"""
        print(f"\n{Colors.BLUE}{'='*80}")
        print(f"  Testing: {Colors.BOLD}{comp1['name']} <-> {comp2['name']}{Colors.END}")
        print(f"{Colors.BLUE}{'='*80}{Colors.END}\n")
        
        # Get theoretical max speed
        speed1 = self.get_link_speed(comp1['name'])
        speed2 = self.get_link_speed(comp2['name'])
        max_theoretical = min(speed1, speed2)
        
        print(f"  {Colors.GRAY}Theoretical maximum: {max_theoretical:.0f} Mbps{Colors.END}\n")
        
        all_results = {}
        
        # Test suite configuration
        test_suite = [
            {
                'name': 'TCP Bandwidth (Single Stream)',
                'params': {'duration': 10},
                'bidirectional': True
            },
            {
                'name': 'TCP Bandwidth (8 Parallel Streams)',
                'params': {'duration': 10, 'parallel': 8},
                'bidirectional': True
            },
            {
                'name': 'UDP Latency/Jitter Test',
                'params': {'duration': 10, 'udp': True, 'bandwidth': f'{int(max_theoretical*0.8)}M'},
                'bidirectional': False
            }
        ]
        
        # Run tests for each configuration
        for test_config in test_suite:
            test_name = test_config['name']
            params = test_config['params']
            
            print(f"  {Colors.CYAN}Running: {test_name}{Colors.END}")
            
            # Test comp1 -> comp2
            if self.verify_iperf_server(comp2['ip']):
                result = self.run_advanced_test(comp1['ip'], comp1['name'], 
                                               comp2['ip'], comp2['name'], params)
                if result:
                    key = f"{comp1['name']}->{comp2['name']} ({test_name})"
                    all_results[key] = result
                    self.print_test_result(key, result, max_theoretical)
            
            # Test reverse direction if bidirectional
            if test_config['bidirectional'] and self.verify_iperf_server(comp1['ip']):
                result = self.run_advanced_test(comp2['ip'], comp2['name'],
                                               comp1['ip'], comp1['name'], params)
                if result:
                    key = f"{comp2['name']}->{comp1['name']} ({test_name})"
                    all_results[key] = result
                    self.print_test_result(key, result, max_theoretical)
                    
        return all_results
    
    def print_test_result(self, connection, result, max_speed):
        """Print detailed test result"""
        bandwidth = result.get('bandwidth', 0)
        utilization = (bandwidth / max_speed) * 100 if max_speed > 0 else 0
        
        # Determine status color
        if utilization >= 90:
            status_color = Colors.GREEN
        elif utilization >= 70:
            status_color = Colors.YELLOW
        else:
            status_color = Colors.RED
        
        # Base metrics
        output = f"    {Colors.WHITE}{connection:<45}{Colors.END} "
        output += f"{status_color}{bandwidth:>8.1f} Mbps ({utilization:>5.1f}%){Colors.END}"
        
        # Additional metrics if available
        metrics = []
        
        if result.get('jitter') is not None:
            metrics.append(f"Jitter: {result['jitter']:.2f}ms")
            
        if result.get('packet_loss') is not None:
            loss = result['packet_loss']
            loss_color = Colors.GREEN if loss < 0.1 else Colors.YELLOW if loss < 1 else Colors.RED
            metrics.append(f"{loss_color}Loss: {loss:.2f}%{Colors.END}")
            
        if result.get('retransmits') is not None:
            retrans = result['retransmits']
            retrans_color = Colors.GREEN if retrans < 10 else Colors.YELLOW if retrans < 100 else Colors.RED
            metrics.append(f"{retrans_color}Retrans: {retrans}{Colors.END}")
            
        if result.get('rtt') is not None:
            metrics.append(f"RTT: {result['rtt']:.1f}ms")
        
        if metrics:
            output += f" | {' | '.join(metrics)}"
            
        print(output)
    
    def get_link_speed(self, comp_name):
        """Get the link speed in Mbps from computer config"""
        for comp in self.computers:
            if comp['name'] == comp_name:
                speed_str = comp.get('link_speed', '1Gbps')
                if 'Gbps' in speed_str:
                    return float(speed_str.replace('Gbps', '')) * 1000
                elif 'Mbps' in speed_str:
                    return float(speed_str.replace('Mbps', ''))
        return 1000
    
    def run_all_tests(self):
        """Test all computer pairs with comprehensive metrics"""
        if len(self.computers) < 2:
            print(f"{Colors.RED}Need at least 2 computers to run tests{Colors.END}")
            return
        
        # Run comprehensive tests for each pair
        for i in range(len(self.computers)):
            for j in range(i+1, len(self.computers)):
                self.run_comprehensive_test(self.computers[i], self.computers[j])
        
        print(f"\n{Colors.CYAN}{'='*80}{Colors.END}")
        print(f"  {Colors.BOLD}TEST COMPLETE{Colors.END}")
        print(f"{Colors.CYAN}{'='*80}{Colors.END}")
        
        # Print summary legend
        print(f"\n{Colors.GRAY}Metrics Explanation:{Colors.END}")
        print(f"  • {Colors.BOLD}Bandwidth{Colors.END}: Data transfer rate (higher is better)")
        print(f"  • {Colors.BOLD}Jitter{Colors.END}: Variation in latency (lower is better, <20ms good)")
        print(f"  • {Colors.BOLD}Packet Loss{Colors.END}: Lost packets (lower is better, <1% good)")
        print(f"  • {Colors.BOLD}Retransmits{Colors.END}: TCP retransmissions (lower is better)")
        print(f"  • {Colors.BOLD}RTT{Colors.END}: Round Trip Time (lower is better)")

def main():
    parser = argparse.ArgumentParser(description='Advanced Network Monitoring Tool')
    parser.add_argument('-u', '--username', required=True, help='SSH username')
    parser.add_argument('-p', '--password', required=True, help='SSH password')
    parser.add_argument('-c', '--config', default='network_config.json', help='Config file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--duration', type=int, default=10, help='Test duration in seconds')
    parser.add_argument('--parallel', type=int, help='Number of parallel streams')
    parser.add_argument('--udp', action='store_true', help='Run UDP tests')
    
    args = parser.parse_args()
    
    monitor = AdvancedNetworkMonitor(args.username, args.password, args.config, args.verbose)
    monitor.run_all_tests()

if __name__ == "__main__":
    main()