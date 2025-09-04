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
            # Disable key-based auth to force password authentication
            ssh.connect(ip, username=self.username, password=self.password, 
                       timeout=10, look_for_keys=False, allow_agent=False)
            if self.verbose:
                print(f"  {Colors.GREEN}[DEBUG] Connected successfully{Colors.END}")
            return ssh
        except paramiko.AuthenticationException as e:
            if show_error:
                print(f"  {Colors.RED}X Authentication failed for {ip}: Check username/password{Colors.END}")
            elif self.verbose:
                print(f"  {Colors.RED}[DEBUG] Auth failed for {ip}: {e}{Colors.END}")
            return None
        except Exception as e:
            if show_error:
                print(f"  {Colors.RED}X Cannot connect to {ip}: {str(e).split(',')[0]}{Colors.END}")
            elif self.verbose:
                print(f"  {Colors.RED}[DEBUG] Failed to connect to {ip}: {e}{Colors.END}")
            return None
            
    def verify_iperf_server(self, server_ip, server_name=None):
        """Verify that iperf3 server is running"""
        ssh = self.ssh_connect(server_ip, show_error=False)
        if not ssh:
            if server_name:
                print(f"  {Colors.RED}X Cannot verify server on {server_name} - SSH connection failed{Colors.END}")
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
                print(f"  {Colors.RED}X Error checking server on {server_name}: {e}{Colors.END}")
            return False
    
    def find_iperf3_path(self, ssh):
        """Find working iperf3 path on the system"""
        paths = [
            r'C:\iperf3\iperf3.19.1_64\iperf3.exe',
            r'C:\iperf3_new\iperf3.exe',
            r'C:\iperf3_fresh\iperf3.19.1_64\iperf3.exe',
            r'C:\iperf3_manual\iperf3.19.1_64\iperf3.exe',
            r'C:\iperf3\iperf3.exe'
        ]
        
        for path in paths:
            stdin, stdout, stderr = ssh.exec_command(f'if exist "{path}" echo FOUND')
            if "FOUND" in stdout.read().decode():
                # Test if it actually runs
                stdin, stdout, stderr = ssh.exec_command(f'"{path}" --version 2>&1', timeout=5)
                output = stdout.read().decode() + stderr.read().decode()
                if "iperf" in output.lower() and "denied" not in output.lower():
                    return path
        return None
    
    def run_advanced_test(self, client_ip, client_name, server_ip, server_name, test_params):
        """Run advanced iperf3 test with specified parameters"""
        ssh = self.ssh_connect(client_ip, show_error=False)
        if not ssh:
            print(f"  {Colors.RED}X Cannot run test from {client_name} - SSH connection failed{Colors.END}")
            return None
            
        try:
            # Find working iperf3 path
            iperf_path = self.find_iperf3_path(ssh)
            if not iperf_path:
                iperf_path = r'C:\iperf3\iperf3.19.1_64\iperf3.exe'  # fallback to default
            
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
                print(f"  {Colors.RED}X Connection refused to {server_name} - server not accepting connections{Colors.END}")
                ssh.close()
                return None
            
            if "Access is denied" in errors:
                print(f"  {Colors.YELLOW}! {client_name} has iperf3 permission issues - skipping test from this host{Colors.END}")
                if self.verbose:
                    print(f"  {Colors.GRAY}[DEBUG] Access denied error - likely antivirus or policy restriction{Colors.END}")
                    print(f"  {Colors.GRAY}[DEBUG] Tests TO this host will still work{Colors.END}")
                ssh.close()
                return None
            
            if "cannot be found" in errors or "not recognized" in errors:
                print(f"  {Colors.RED}X iperf3 not found on {client_name} - needs installation{Colors.END}")
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
            'rtt': None,
            'cwnd': None,  # Congestion window
            'mss': None,    # Maximum segment size
            'pmtu': None    # Path MTU
        }
        
        try:
            end_data = json_data.get('end', {})
            
            if test_params.get('udp'):
                # UDP test results
                streams = end_data.get('sum', {})
                results['bandwidth'] = streams.get('bits_per_second', 0) / 1000000  # Convert to Mbps
                results['jitter'] = streams.get('jitter_ms', 0)
                results['packet_loss'] = streams.get('lost_percent', 0)
                results['packets_sent'] = streams.get('packets', 0)
                results['packets_lost'] = streams.get('lost_packets', 0)
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
                
                # Try to get RTT and TCP metrics from streams
                streams = end_data.get('streams', [])
                if streams and len(streams) > 0:
                    stream = streams[0]
                    sender = stream.get('sender', {})
                    
                    # Debug: Print available keys in verbose mode
                    if self.verbose:
                        print(f"  {Colors.GRAY}[DEBUG] TCP stream keys: {list(sender.keys())[:10]}{Colors.END}")
                    
                    if 'mean_rtt' in sender:
                        results['rtt'] = sender.get('mean_rtt', 0) / 1000  # Convert to ms
                    if 'max_snd_cwnd' in sender:
                        results['cwnd'] = sender.get('max_snd_cwnd', 0) / 1024  # Convert to KB
                    if 'max_rtt' in sender:
                        results['max_rtt'] = sender.get('max_rtt', 0) / 1000  # Convert to ms
                    if 'min_rtt' in sender:
                        results['min_rtt'] = sender.get('min_rtt', 0) / 1000  # Convert to ms
                        
                # Get connection info
                connected = json_data.get('start', {}).get('connected', [])
                if connected and len(connected) > 0:
                    results['mss'] = connected[0].get('mss', None)
                    results['pmtu'] = connected[0].get('pmtu', None)
                        
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
        """Display test results in ultra-compact single-row format"""
        # Get unique connections
        connections = sorted(set([k for t in test_results.values() for k in t.keys()]))
        
        for connection in connections:
            # Get both TCP and UDP results for this connection
            tcp_data = test_results['tcp'].get(connection, (None, 0))
            udp_data = test_results['udp_jitter'].get(connection, (None, 0))
            
            if tcp_data[0] or udp_data[0]:
                self.print_single_row_result(connection, tcp_data, udp_data)
    
    def print_single_row_result(self, connection, tcp_data, udp_data):
        """Print all test results for a connection in a single compact row"""
        tcp_result, tcp_max = tcp_data
        udp_result, udp_max = udp_data
        
        # Start with connection name
        row = f"  {Colors.WHITE}{connection:28}{Colors.END} "
        
        # TCP Section
        if tcp_result:
            tcp_bw = tcp_result.get('bandwidth', 0)
            tcp_util = (tcp_bw / tcp_max) * 100 if tcp_max > 0 else 0
            retrans = tcp_result.get('retransmits')
            
            # TCP color coding
            if tcp_util >= 90:
                tcp_color = Colors.GREEN
            elif tcp_util >= 70:
                tcp_color = Colors.YELLOW  
            else:
                tcp_color = Colors.RED
            
            row += f"T:{tcp_color}{tcp_bw:4.0f}M/{tcp_util:3.0f}%{Colors.END}"
            if retrans is not None and retrans > 0:
                row += f"{Colors.YELLOW}(R{retrans}){Colors.END}"
            row += " "
        else:
            row += f"T:{Colors.GRAY}----/---%{Colors.END}     "
        
        # UDP Section
        if udp_result:
            udp_bw = udp_result.get('bandwidth', 0)
            udp_util = (udp_bw / udp_max) * 100 if udp_max > 0 else 0
            jitter = udp_result.get('jitter', 0)
            loss = udp_result.get('packet_loss', 0)
            
            # UDP color coding
            if udp_util >= 90:
                udp_color = Colors.GREEN
            elif udp_util >= 70:
                udp_color = Colors.YELLOW
            else:
                udp_color = Colors.RED
                
            # Jitter color
            if jitter < 1:
                j_color = Colors.GREEN
            elif jitter < 5:
                j_color = Colors.YELLOW
            else:
                j_color = Colors.RED
            
            # Loss indicator - always show
            if loss > 1:
                loss_color = Colors.RED
                loss_str = f"L:{loss:.1f}%"
            elif loss > 0.01:
                loss_color = Colors.YELLOW
                loss_str = f"L:{loss:.2f}%"
            else:
                loss_color = Colors.GREEN
                loss_str = f"L:{loss:.2f}%"
                
            row += f"U:{udp_color}{udp_bw:4.0f}M/{udp_util:3.0f}%{Colors.END} "
            row += f"J:{j_color}{jitter:4.2f}ms{Colors.END} {loss_color}{loss_str}{Colors.END}"
        else:
            row += f"U:{Colors.GRAY}----/---%{Colors.END} J:{Colors.GRAY}----ms{Colors.END} {Colors.GRAY}L:---%{Colors.END}"
        
        # Additional metrics (from either TCP or UDP result)
        result = tcp_result if tcp_result else udp_result
        
        if result:
            # RTT (Round Trip Time) - TCP only
            if result.get('rtt') is not None:
                rtt = result['rtt']
                if rtt < 1:
                    rtt_color = Colors.GREEN
                elif rtt < 10:
                    rtt_color = Colors.YELLOW
                else:
                    rtt_color = Colors.RED
                row += f" RTT:{rtt_color}{rtt:.1f}ms{Colors.END}"
            
            # CPU Usage
            if result.get('cpu_usage'):
                cpu_local = result['cpu_usage'].get('local', 0)
                cpu_remote = result['cpu_usage'].get('remote', 0)
                cpu_color = Colors.GREEN if cpu_local < 50 else Colors.YELLOW if cpu_local < 80 else Colors.RED
                row += f" CPU:{cpu_color}{cpu_local:.0f}%/{cpu_remote:.0f}%{Colors.END}"
            
            # Congestion Window (TCP only)
            if result.get('cwnd') is not None:
                cwnd = result['cwnd']
                row += f" CW:{Colors.CYAN}{cwnd:.0f}KB{Colors.END}"
            
            # MSS/MTU info (TCP only)
            if result.get('mss'):
                row += f" MSS:{Colors.GRAY}{result['mss']}{Colors.END}"
            
        print(row)
    
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
        
        print(f"\n{Colors.CYAN}{'='*90}")
        print(f"{'NETWORK PERFORMANCE TESTS':^90}")
        print(f"{'='*90}{Colors.END}\n")
        
        print(f"{Colors.GRAY}Legend: T=TCP U=UDP | BW/% | J=Jitter L=Loss R=Retrans | RTT=Latency CPU=Local/Remote CW=CongestionWindow MSS=MaxSegSize{Colors.END}")
        print(f"{Colors.GRAY}{'Connection':<30} {'TCP Test':<15} {'UDP Test':<25} {'Extended Metrics':<30}{Colors.END}")
        print(f"{Colors.GRAY}{'-'*90}{Colors.END}")
        
        # Run comprehensive tests for each pair
        test_count = 0
        for i in range(len(self.computers)):
            for j in range(i+1, len(self.computers)):
                test_count += 1
                self.run_comprehensive_test(self.computers[i], self.computers[j])
        
        print(f"\n{Colors.CYAN}{'='*90}")
        print(f"{'TESTS COMPLETE':^90}")
        print(f"{'='*90}{Colors.END}")
        
        # Summary
        print(f"\n{Colors.GRAY}Key Indicators:{Colors.END}")
        print(f"  {Colors.GREEN}Green{Colors.END}: Excellent (>90% bandwidth, <1ms jitter)")
        print(f"  {Colors.YELLOW}Yellow{Colors.END}: Acceptable (70-90% bandwidth, <5ms jitter)")
        print(f"  {Colors.RED}Red{Colors.END}: Issues detected (check loss/retransmits)")
    
    def check_adapter_settings(self, computer_ip, computer_name):
        """Check network adapter settings for optimal AV network performance"""
        ssh = self.ssh_connect(computer_ip, show_error=True)
        if not ssh:
            return None
        
        try:
            results = {
                'name': computer_name,
                'ip': computer_ip,
                'adapters': [],
                'warnings': []
            }
            
            # Get all network adapters (including WiFi)
            ps_cmd = 'powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, LinkSpeed, FullDuplex, MediaType, PhysicalMediaType | ConvertTo-Json"'
            stdin, stdout, stderr = ssh.exec_command(ps_cmd, timeout=30)
            adapter_json = stdout.read().decode()
            error = stderr.read().decode()
            
            # Check if access is denied
            if ('Access denied' in error or 'Access is denied' in error or 
                'cannot be loaded' in error or not adapter_json):
                # PowerShell/WMI access denied - return limited info
                results['warnings'].append(f"Limited access - cannot check adapter settings (requires elevated permissions)")
                results['adapters'].append({
                    'name': 'Unknown',
                    'description': 'Access Denied',
                    'link_speed': 'Unknown',
                    'full_duplex': True,
                    'settings': {
                        'power_management': 'Unable to check',
                        'eee': 'Unable to check',
                        'jumbo_frames': 'Unable to check'
                    }
                })
                ssh.close()
                return results
            
            if adapter_json:
                try:
                    import json
                    adapters = json.loads(adapter_json)
                    if not isinstance(adapters, list):
                        adapters = [adapters]
                    
                    for adapter in adapters:
                        name = adapter.get('Name', 'Unknown')
                        desc = adapter.get('InterfaceDescription', '')
                        status = adapter.get('Status', '')
                        media = adapter.get('PhysicalMediaType', '')
                        
                        # Check if it's a WiFi adapter
                        is_wifi = False
                        if 'Wi-Fi' in name or 'WiFi' in name or 'Wireless' in desc or 'Wi-Fi' in desc:
                            is_wifi = True
                        elif media and ('wireless' in media.lower() or '802.11' in media.lower()):
                            is_wifi = True
                        
                        # Skip disconnected adapters unless they're WiFi (we want to show WiFi even if disabled)
                        if status != 'Up' and not is_wifi:
                            continue
                        
                        # For WiFi adapters, warn if they're enabled
                        if is_wifi:
                            if status == 'Up':
                                results['warnings'].append(f"{name}: WiFi adapter is ENABLED (should be disabled for AV networks)")
                            # Add WiFi adapter info even if disabled to show it's properly configured
                            adapter_info = {
                                'name': name,
                                'description': desc,
                                'link_speed': 'WiFi - ' + ('ENABLED' if status == 'Up' else 'Disabled'),
                                'full_duplex': True,
                                'settings': {
                                    'power_management': 'N/A',
                                    'eee': 'N/A',
                                    'jumbo_frames': 'N/A',
                                    'wifi_status': status
                                }
                            }
                            results['adapters'].append(adapter_info)
                            continue
                        
                        # For Ethernet adapters
                        adapter_info = {
                            'name': name,
                            'description': desc,
                            'link_speed': adapter.get('LinkSpeed', 'Unknown'),
                            'full_duplex': adapter.get('FullDuplex', True),
                            'settings': {}
                        }
                        
                        # Check power management settings
                        pm_cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetAdapterPowerManagement -Name \'{adapter_info["name"]}\' | Select-Object AllowComputerToTurnOffDevice | ConvertTo-Json"'
                        stdin, stdout, stderr = ssh.exec_command(pm_cmd, timeout=30)
                        pm_output = stdout.read().decode()
                        
                        if pm_output:
                            try:
                                pm_data = json.loads(pm_output)
                                power_mgmt = pm_data.get('AllowComputerToTurnOffDevice', 'Unknown')
                                adapter_info['settings']['power_management'] = power_mgmt
                                
                                if power_mgmt == 'Enabled' or power_mgmt == True:
                                    results['warnings'].append(f"{adapter_info['name']}: Power saving enabled (can cause dropouts)")
                            except:
                                adapter_info['settings']['power_management'] = 'Unknown'
                        
                        # Check EEE/Green Ethernet settings
                        eee_cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetAdapterAdvancedProperty -Name \'{adapter_info["name"]}\' | Where-Object {{$_.DisplayName -like \'*Energy*\' -or $_.DisplayName -like \'*EEE*\' -or $_.DisplayName -like \'*Green*\'}} | Select-Object DisplayName, DisplayValue | ConvertTo-Json"'
                        stdin, stdout, stderr = ssh.exec_command(eee_cmd, timeout=30)
                        eee_output = stdout.read().decode()
                        
                        if eee_output:
                            try:
                                eee_data = json.loads(eee_output)
                                if not isinstance(eee_data, list):
                                    eee_data = [eee_data] if eee_data else []
                                
                                for setting in eee_data:
                                    name = setting.get('DisplayName', '')
                                    value = setting.get('DisplayValue', '')
                                    
                                    if 'energy' in name.lower() or 'eee' in name.lower() or 'green' in name.lower():
                                        adapter_info['settings']['eee'] = value
                                        if value.lower() in ['enabled', 'on', 'yes', 'true']:
                                            results['warnings'].append(f"{adapter_info['name']}: {name} is {value} (incompatible with Dante/NDI)")
                            except:
                                pass
                        
                        # Check Jumbo Frames
                        jumbo_cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetAdapterAdvancedProperty -Name \'{adapter_info["name"]}\' | Where-Object {{$_.DisplayName -like \'*Jumbo*\' -or $_.DisplayName -like \'*MTU*\'}} | Select-Object DisplayName, DisplayValue | ConvertTo-Json"'
                        stdin, stdout, stderr = ssh.exec_command(jumbo_cmd, timeout=30)
                        jumbo_output = stdout.read().decode()
                        
                        if jumbo_output:
                            try:
                                jumbo_data = json.loads(jumbo_output)
                                if jumbo_data:
                                    if not isinstance(jumbo_data, list):
                                        jumbo_data = [jumbo_data]
                                    for setting in jumbo_data:
                                        if 'jumbo' in setting.get('DisplayName', '').lower():
                                            adapter_info['settings']['jumbo_frames'] = setting.get('DisplayValue', 'Unknown')
                            except:
                                pass
                        
                        results['adapters'].append(adapter_info)
                        
                except Exception as e:
                    if self.verbose:
                        print(f"  {Colors.RED}[DEBUG] Error parsing adapter data: {e}{Colors.END}")
            
            ssh.close()
            return results
            
        except Exception as e:
            if self.verbose:
                print(f"  {Colors.RED}[DEBUG] Error checking adapter settings: {e}{Colors.END}")
            ssh.close()
            return None
    
    def check_all_adapters(self):
        """Check network adapter settings on all computers"""
        print(f"\n{Colors.CYAN}{'='*90}")
        print(f"{'NETWORK ADAPTER CONFIGURATION CHECK':^90}")
        print(f"{'='*90}{Colors.END}\n")
        
        # Header
        print(f"{Colors.GRAY}{'Computer':<20} {'Speed':<12} {'PowerMgmt':<12} {'EEE/Green':<12} {'Jumbo':<10} {'Status':<20}{Colors.END}")
        print(f"{Colors.GRAY}{'-'*90}{Colors.END}")
        
        all_warnings = []
        
        for computer in self.computers:
            results = self.check_adapter_settings(computer['ip'], computer['name'])
            
            if results and results['adapters']:
                # Add any warnings from the results
                for warning in results.get('warnings', []):
                    if warning not in all_warnings:
                        all_warnings.append(warning)
                
                for adapter in results['adapters']:
                    # Build compact row
                    row = f"{Colors.WHITE}{computer['name']:<20}{Colors.END} "
                    
                    # Link speed
                    speed = adapter['link_speed']
                    if 'WiFi - ENABLED' in speed:
                        speed_str = "WiFi ON"
                        speed_color = Colors.RED
                    elif 'WiFi - Disabled' in speed:
                        speed_str = "WiFi OFF"
                        speed_color = Colors.GREEN
                    elif speed == 'Unknown':
                        speed_str = "Access Denied"
                        speed_color = Colors.YELLOW
                    elif '10 Gbps' in speed:
                        speed_str = "10Gbps"
                        speed_color = Colors.GREEN
                    elif '2.5 Gbps' in speed:
                        speed_str = "2.5Gbps"
                        speed_color = Colors.GREEN
                    elif '1 Gbps' in speed:
                        speed_str = "1Gbps"
                        speed_color = Colors.GREEN
                    else:
                        speed_str = speed[:10] if len(speed) > 10 else speed
                        speed_color = Colors.YELLOW
                    row += f"{speed_color}{speed_str:<12}{Colors.END} "
                    
                    # Power Management
                    pm_status = adapter['settings'].get('power_management', 'Unknown')
                    if pm_status == 'N/A':
                        row += f"{Colors.GRAY}{'-':<12}{Colors.END} "
                    elif pm_status in ['Disabled', 'NotSupported', False]:
                        row += f"{Colors.GREEN}{'Disabled':<12}{Colors.END} "
                    elif pm_status in ['Enabled', True]:
                        row += f"{Colors.RED}{'Enabled':<12}{Colors.END} "
                        if 'wifi_status' not in adapter['settings']:  # Don't double-warn for WiFi
                            all_warnings.append(f"{computer['name']}: Power saving enabled on {adapter['name']}")
                    else:
                        row += f"{Colors.GRAY}{'Unknown':<12}{Colors.END} "
                    
                    # EEE/Green Ethernet
                    eee_status = adapter['settings'].get('eee', 'Not Found')
                    if eee_status == 'N/A':
                        row += f"{Colors.GRAY}{'-':<12}{Colors.END} "
                    elif eee_status.lower() in ['disabled', 'off', 'no', 'false']:
                        row += f"{Colors.GREEN}{'Disabled':<12}{Colors.END} "
                    elif eee_status.lower() in ['enabled', 'on', 'yes', 'true']:
                        row += f"{Colors.RED}{'Enabled':<12}{Colors.END} "
                        all_warnings.append(f"{computer['name']}: EEE/Green enabled on {adapter['name']}")
                    else:
                        row += f"{Colors.GRAY}{'-':<12}{Colors.END} "
                    
                    # Jumbo Frames
                    jumbo_status = adapter['settings'].get('jumbo_frames', 'Not Found')
                    if jumbo_status == 'N/A':
                        row += f"{Colors.GRAY}{'-':<10}{Colors.END} "
                    elif jumbo_status != 'Not Found':
                        if 'disabled' in jumbo_status.lower():
                            row += f"{Colors.GREEN}{'Disabled':<10}{Colors.END} "
                        else:
                            row += f"{Colors.YELLOW}{jumbo_status[:9]:<10}{Colors.END} "
                    else:
                        row += f"{Colors.GRAY}{'-':<10}{Colors.END} "
                    
                    # Overall status
                    wifi_status = adapter['settings'].get('wifi_status', None)
                    if wifi_status == 'Up':
                        row += f"{Colors.RED}WiFi ENABLED!{Colors.END}"
                    elif wifi_status in ['Disconnected', 'Not Present']:
                        row += f"{Colors.GREEN}WiFi disabled{Colors.END}"
                    elif not any(w.startswith(computer['name']) for w in all_warnings):
                        row += f"{Colors.GREEN}OK{Colors.END}"
                    else:
                        row += f"{Colors.YELLOW}! Check settings{Colors.END}"
                    
                    print(row)
            else:
                print(f"{Colors.WHITE}{computer['name']:<20}{Colors.END} {Colors.RED}{'Connection failed':<60}{Colors.END}")
        
        # Summary
        print(f"\n{Colors.CYAN}{'='*90}")
        print(f"{'CONFIGURATION SUMMARY':^90}")
        print(f"{'='*90}{Colors.END}\n")
        
        if all_warnings:
            print(f"{Colors.YELLOW}[!] Issues Found:{Colors.END}")
            for warning in all_warnings:
                print(f"  - {warning}")
            print(f"\n{Colors.GRAY}Recommendations:{Colors.END}")
            print(f"  1. Disable all WiFi adapters for AV networks")
            print(f"  2. Disable 'Allow computer to turn off device' in adapter properties")
            print(f"  3. Disable Energy Efficient Ethernet (EEE/Green Ethernet)")
            print(f"  4. For NDI: Disable Jumbo Frames to avoid fragmentation")
            print(f"  5. Ensure all adapters are set to 1Gbps Full Duplex or higher")
        else:
            print(f"{Colors.GREEN}[OK] All network adapters are optimally configured!{Colors.END}")

def main():
    parser = argparse.ArgumentParser(description='Advanced Network Monitoring Tool')
    parser.add_argument('-u', '--username', required=True, help='SSH username')
    parser.add_argument('-p', '--password', required=True, help='SSH password')
    parser.add_argument('-c', '--config', default='network_config.json', help='Config file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--duration', type=int, default=10, help='Test duration in seconds')
    parser.add_argument('--parallel', type=int, help='Number of parallel streams')
    parser.add_argument('--udp', action='store_true', help='Run UDP tests')
    parser.add_argument('--no-adapter-check', action='store_true', help='Skip network adapter configuration check')
    parser.add_argument('--adapters-only', action='store_true', help='Only check adapters, skip bandwidth tests')
    
    args = parser.parse_args()
    
    monitor = AdvancedNetworkMonitor(args.username, args.password, args.config, args.verbose)
    
    if args.adapters_only:
        # Only check adapter settings
        monitor.check_all_adapters()
    elif args.no_adapter_check:
        # Skip adapter check and just run bandwidth tests
        monitor.run_all_tests()
    else:
        # Default: Check adapters first, then run tests
        monitor.check_all_adapters()
        print(f"\n{Colors.CYAN}{'='*90}{Colors.END}")
        print(f"{Colors.BOLD}Proceeding with bandwidth tests...{Colors.END}\n")
        monitor.run_all_tests()

if __name__ == "__main__":
    main()