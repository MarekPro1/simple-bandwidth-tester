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
                
                # Always show device list nicely
                print(f"\n{Colors.CYAN}{'='*70}")
                print(f"{'NETWORK PERFORMANCE MONITOR':^70}")
                print(f"{'='*70}{Colors.END}\n")
                
                print(f"{Colors.WHITE}Configured Devices ({len(self.computers)} computers):{Colors.END}\n")
                
                # Display devices in a nice table format
                print(f"  {Colors.GRAY}{'Name':<15} {'IP Address':<15} {'Link Speed':<10} {'Location':<10}{Colors.END}")
                print(f"  {Colors.GRAY}{'-'*15} {'-'*15} {'-'*10} {'-'*10}{Colors.END}")
                
                for comp in self.computers:
                    name = comp['name'][:15]
                    ip = comp['ip']
                    link_speed = comp.get('link_speed', 'Unknown')
                    location = comp.get('location', 'Unknown')
                    
                    # Color code based on link speed
                    if '10Gbps' in link_speed:
                        speed_color = Colors.GREEN
                    elif '2.5Gbps' in link_speed or '5Gbps' in link_speed:
                        speed_color = Colors.CYAN
                    else:
                        speed_color = Colors.YELLOW
                    
                    print(f"  {Colors.BOLD}{name:<15}{Colors.END} "
                          f"{Colors.GRAY}{ip:<15}{Colors.END} "
                          f"{speed_color}{link_speed:<10}{Colors.END} "
                          f"{Colors.YELLOW}{location:<10}{Colors.END}")
                
        except Exception as e:
            print(f"{Colors.RED}Error loading config: {e}{Colors.END}")
            sys.exit(1)
            
    def ssh_connect(self, ip, show_error=True):
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
            if show_error:
                print(f"  {Colors.RED}✗ Cannot connect to {ip}: {str(e).split(',')[0]}{Colors.END}")
            elif self.verbose:
                print(f"  {Colors.RED}[DEBUG] Failed to connect to {ip}: {e}{Colors.END}")
            return None
            
    def verify_iperf_server(self, server_ip, server_name=None):
        """Verify that iperf3 server is running"""
        ssh = self.ssh_connect(server_ip, show_error=False)
        if not ssh:
            if server_name:
                print(f"  {Colors.RED}✗ Cannot verify server on {server_name} - SSH connection failed{Colors.END}")
            return False
            
        try:
            stdin, stdout, stderr = ssh.exec_command('netstat -an | findstr :5201')
            netstat_output = stdout.read().decode()
            ssh.close()
            
            is_listening = "5201" in netstat_output and "LISTENING" in netstat_output
            
            if not is_listening and server_name:
                print(f"  {Colors.YELLOW}⚠ No iperf3 server running on {server_name} ({server_ip}){Colors.END}")
            elif self.verbose and is_listening:
                print(f"  {Colors.GREEN}[DEBUG] Server ready on {server_ip}{Colors.END}")
            
            return is_listening
                
        except Exception as e:
            ssh.close()
            if server_name:
                print(f"  {Colors.RED}✗ Error checking server on {server_name}: {e}{Colors.END}")
            return False
    
    def run_advanced_test(self, client_ip, client_name, server_ip, server_name, test_params):
        """Run advanced iperf3 test with specified parameters"""
        ssh = self.ssh_connect(client_ip, show_error=False)
        if not ssh:
            print(f"  {Colors.RED}✗ Cannot run test from {client_name} - SSH connection failed{Colors.END}")
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
                if test_params.get('length'):
                    cmd_parts.append(f'-l {test_params["length"]}')  # Packet length
                
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
            
            # Check for common errors
            if "Connection refused" in errors or "Connection refused" in output:
                print(f"  {Colors.RED}✗ Connection refused to {server_name} - server not accepting connections{Colors.END}")
                ssh.close()
                return None
            
            if "Access is denied" in errors:
                print(f"  {Colors.RED}✗ Access denied on {client_name} - cannot run iperf3 (permission issue){Colors.END}")
                ssh.close()
                return None
            
            if "cannot be found" in errors or "not recognized" in errors:
                print(f"  {Colors.RED}✗ iperf3 not found on {client_name} - needs installation{Colors.END}")
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
        # Get theoretical max speed
        speed1 = self.get_link_speed(comp1['name'])
        speed2 = self.get_link_speed(comp2['name'])
        max_theoretical = min(speed1, speed2)
        
        all_results = {}
        
        # Test suite optimized for network stress testing
        test_suite = [
            {
                'name': 'TCP Bandwidth',
                'params': {'duration': 5},
                'bidirectional': True
            },
            {
                'name': 'UDP Jitter/Loss Test',
                'params': {
                    'duration': 5, 
                    'udp': True, 
                    'bandwidth': f'{int(max_theoretical * 0.9)}M',  # 90% of link speed
                    'length': 1400  # Standard packet size
                },
                'bidirectional': True
            }
        ]
        
        # Store all results first, then display in organized table
        test_results = {
            'tcp': {},
            'udp_jitter': {},
            'packet_loss': {}
        }
        
        # Run tests for each configuration
        for test_config in test_suite:
            test_name = test_config['name']
            params = test_config['params']
            
            # Determine test type for storage
            if 'UDP' in test_name:
                test_type = 'udp_jitter'
            else:
                test_type = 'tcp'
            
            # Test comp1 -> comp2
            if self.verify_iperf_server(comp2['ip'], comp2['name']):
                result = self.run_advanced_test(comp1['ip'], comp1['name'], 
                                               comp2['ip'], comp2['name'], params)
                if result:
                    key = f"{comp1['name']} -> {comp2['name']}"
                    test_results[test_type][key] = (result, max_theoretical)
            
            # Test reverse direction if bidirectional
            if test_config['bidirectional'] and self.verify_iperf_server(comp1['ip'], comp1['name']):
                result = self.run_advanced_test(comp2['ip'], comp2['name'],
                                               comp1['ip'], comp1['name'], params)
                if result:
                    key = f"{comp2['name']} -> {comp1['name']}"
                    test_results[test_type][key] = (result, max_theoretical)
        
        # Display results in compact table
        self.display_compact_results(test_results, comp1['name'], comp2['name'])
        return test_results
    
    def display_compact_results(self, test_results, name1, name2):
        """Display test results in compact table format"""
        print()  # Just a blank line between test pairs
        
        # Display each connection's results
        for connection in set([k for t in test_results.values() for k in t.keys()]):
            # TCP results
            if connection in test_results['tcp']:
                result, max_speed = test_results['tcp'][connection]
                bandwidth = result.get('bandwidth', 0)
                util = (bandwidth / max_speed) * 100
                
                # Color based on utilization
                if util >= 90:
                    color = Colors.GREEN
                elif util >= 70:
                    color = Colors.YELLOW
                else:
                    color = Colors.RED
                
                output = f"  {Colors.GRAY}[TCP]{Colors.END} {Colors.WHITE}{connection:<30}{Colors.END} "
                output += f"{color}{bandwidth:>6.0f}M ({util:>3.0f}%){Colors.END}"
                
                # Add retransmits if present
                if result.get('retransmits') is not None and result['retransmits'] > 0:
                    output += f" {Colors.YELLOW}Retrans:{result['retransmits']}{Colors.END}"
                    
                print(output)
            
            # UDP/Jitter results
            if connection in test_results['udp_jitter']:
                result, max_speed = test_results['udp_jitter'][connection]
                bandwidth = result.get('bandwidth', 0)
                util = (bandwidth / max_speed) * 100
                jitter = result.get('jitter', 0)
                loss = result.get('packet_loss', 0)
                
                # Bandwidth color
                if util >= 90:
                    bw_color = Colors.GREEN
                elif util >= 70:
                    bw_color = Colors.YELLOW
                else:
                    bw_color = Colors.RED
                
                # Jitter color (Dante needs <1ms, NDI <5ms)
                if jitter < 1:
                    j_color = Colors.GREEN
                elif jitter < 5:
                    j_color = Colors.YELLOW
                else:
                    j_color = Colors.RED
                    
                output = f"  {Colors.GRAY}[UDP]{Colors.END} {Colors.WHITE}{connection:<30}{Colors.END} "
                output += f"{bw_color}{bandwidth:>6.0f}M ({util:>3.0f}%){Colors.END}"
                output += f" Jitter:{j_color}{jitter:.2f}ms{Colors.END}"
                
                # Only show packet loss if > 0
                if loss > 0.01:  # Show if greater than 0.01%
                    output += f" {Colors.RED}Loss:{loss:.2f}%{Colors.END}"
                    
                print(output)
    
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
        
        print(f"\n{Colors.CYAN}{'='*70}")
        print(f"{'STARTING TESTS':^70}")
        print(f"{'='*70}{Colors.END}\n")
        
        print(f"{Colors.GRAY}Test Configuration:{Colors.END}")
        print(f"  • TCP Bandwidth Test (5 seconds)")
        print(f"  • UDP Test at 90% link speed (5 seconds)")
        print(f"  • Target: Jitter <1ms, Loss 0%, No retransmits")
        
        # Run comprehensive tests for each pair
        test_count = 0
        for i in range(len(self.computers)):
            for j in range(i+1, len(self.computers)):
                test_count += 1
                self.run_comprehensive_test(self.computers[i], self.computers[j])
        
        print(f"\n{Colors.CYAN}{'='*70}")
        print(f"{'TESTS COMPLETE':^70}")
        print(f"{'='*70}{Colors.END}")
        
        # Summary
        print(f"\n{Colors.GRAY}Key Indicators:{Colors.END}")
        print(f"  {Colors.GREEN}Green{Colors.END}: Excellent (>90% bandwidth, <1ms jitter)")
        print(f"  {Colors.YELLOW}Yellow{Colors.END}: Acceptable (70-90% bandwidth, <5ms jitter)")
        print(f"  {Colors.RED}Red{Colors.END}: Issues detected (check loss/retransmits)")

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