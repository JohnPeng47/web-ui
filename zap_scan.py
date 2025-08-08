#!/usr/bin/env python3

import requests
import time
import json
from urllib.parse import urlparse

# ZAP API configuration
ZAP_PROXY = "http://localhost:8080"  # Default ZAP proxy address
API_KEY = None  # Set this if you have API key authentication enabled

# URLs to test
urls = [
    "https://0adf009d048f0590816293d700120098.web-security-academy.net",
    "https://0a0400de03dac754811d9e2700c600e3.web-security-academy.net", 
    "https://0ad500340381062e80f9fee400500058.web-security-academy.net",
    "https://0aec006904d646208267abe80063005f.web-security-academy.net"
]

class ZAPTester:
    def __init__(self, proxy_url, api_key=None):
        self.proxy_url = proxy_url
        self.api_key = api_key
        self.ajax_scan_ids = {}
        self.active_scan_ids = {}
        
    def _make_request(self, endpoint, params=None):
        """Make API request to ZAP with error handling"""
        if params is None:
            params = {}
        if self.api_key:
            params['apikey'] = self.api_key
            
        try:
            response = requests.get(f"{self.proxy_url}{endpoint}", params=params)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"HTTP {response.status_code}: {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None
    
    def check_connection(self):
        """Verify ZAP is running and accessible"""
        result = self._make_request("/JSON/core/view/version/")
        if result:
            print(f"✓ Connected to ZAP version: {result.get('version', 'Unknown')}")
            return True
        else:
            return False
            print("❌ Cannot connect to ZAP. Make sure it's running on localhost:8080")
    
    def add_url(self, url):
        """Add URL to ZAP's Sites tree"""
        params = {'url': url, 'followRedirects': 'true'}
        result = self._make_request("/JSON/core/action/accessUrl/", params)
        
        if result and result.get('Result') == 'OK':
            print(f"✓ Added URL: {url}")
            return True
        else:
            print(f"✗ Failed to add URL: {url}")
            return False
    
    def start_ajax_spider(self, url):
        """Start AJAX Spider scan on URL"""
        params = {
            'url': url,
            'inScope': 'true',
            'contextName': '',
            'subtreeOnly': 'false'
        }
        
        result = self._make_request("/JSON/ajaxSpider/action/scan/", params)
        if result and result.get('Result') == 'OK':
            print(f"✓ Started AJAX Spider for: {url}")
            return True
        else:
            print(f"✗ Failed to start AJAX Spider for: {url}")
            return False
    
    def wait_for_ajax_spider(self):
        """Wait for AJAX Spider to complete"""
        print("\nWaiting for AJAX Spider to complete...")
        while True:
            result = self._make_request("/JSON/ajaxSpider/view/status/")
            if result:
                status = result.get('status', 'Unknown')
                print(f"AJAX Spider status: {status}")
                
                if status == 'stopped':
                    break
            time.sleep(5)
        
        # Get results
        result = self._make_request("/JSON/ajaxSpider/view/numberOfResults/")
        if result:
            count = result.get('numberOfResults', '0')
            print(f"✓ AJAX Spider completed. Found {count} URLs")
    
    def start_active_scan(self, url):
        """Start Active Scan on URL"""
        params = {
            'url': url,
            'recurse': 'true',
            'inScopeOnly': 'false',
            'scanPolicyName': '',
            'method': 'GET'
        }
        
        result = self._make_request("/JSON/ascan/action/scan/", params)
        if result:
            scan_id = result.get('scan')
            if scan_id:
                self.active_scan_ids[url] = scan_id
                print(f"✓ Started Active Scan {scan_id} for: {url}")
                return scan_id
        
        print(f"✗ Failed to start Active Scan for: {url}")
        return None
    
    def wait_for_active_scans(self):
        """Wait for all active scans to complete"""
        print(f"\nWaiting for {len(self.active_scan_ids)} active scans to complete...")
        
        while self.active_scan_ids:
            completed_scans = []
            
            for url, scan_id in self.active_scan_ids.items():
                params = {'scanId': scan_id}
                result = self._make_request("/JSON/ascan/view/status/", params)
                
                if result:
                    progress = result.get('status', '0')
                    print(f"Scan {scan_id} ({self._get_hostname(url)}): {progress}%")
                    
                    if progress == '100':
                        completed_scans.append(url)
            
            # Remove completed scans
            for url in completed_scans:
                print(f"✓ Completed scan for: {url}")
                del self.active_scan_ids[url]
            
            if self.active_scan_ids:  # Still have running scans
                time.sleep(10)
        
        print("✓ All active scans completed!")
    
    def _get_hostname(self, url):
        """Extract hostname from URL for display"""
        return urlparse(url).netloc
    
    def generate_reports(self):
        """Generate individual reports for each URL"""
        print("\nGenerating reports...")
        
        for url in urls:
            hostname = self._get_hostname(url)
            print(f"\n{'='*60}")
            print(f"SECURITY REPORT FOR: {hostname}")
            print(f"URL: {url}")
            print(f"{'='*60}")
            
            # Get alerts for this specific site
            params = {'baseurl': url}
            result = self._make_request("/JSON/core/view/alerts/", params)
                
            if result and 'alerts' in result:
                alerts = result['alerts']
                
                if not alerts:
                    print("✅ No security issues found!")
                    continue
                
                # Group alerts by risk level
                risk_groups = {}
                for alert in alerts:
                    risk = alert.get('risk', 'Unknown')
                    if risk not in risk_groups:
                        risk_groups[risk] = []
                    risk_groups[risk].append(alert)
                
                # Display results by risk level
                risk_order = ['High', 'Medium', 'Low', 'Informational']
                
                for risk_level in risk_order:
                    if risk_level in risk_groups:
                        count = len(risk_groups[risk_level])
                        print(f"\n🚨 {risk_level.upper()} RISK ({count} issues):")
                        print("-" * 40)
                        
                        for alert in risk_groups[risk_level]:
                            name = alert.get('name', 'Unknown Issue')
                            confidence = alert.get('confidence', 'Unknown')
                            description = alert.get('description', 'No description')
                            
                            print(f"• {name}")
                            print(f"  Confidence: {confidence}")
                            print(f"  Description: {description[:100]}...")
                            
                            # Show affected URLs (first few)
                            instances = alert.get('instances', [])
                            if instances:
                                print(f"  Affected URLs ({len(instances)} total):")
                                for i, instance in enumerate(instances[:3]):  # Show first 3
                                    print(f"    - {instance.get('uri', 'Unknown')}")
                                if len(instances) > 3:
                                    print(f"    ... and {len(instances) - 3} more")
                            print()
            else:
                print("❌ Could not retrieve alerts for this URL")
        
        # Generate summary report
        self._generate_summary_report()
    
    def _generate_summary_report(self):
        """Generate overall summary report"""
        print(f"\n{'='*60}")
        print("OVERALL SECURITY SUMMARY")
        print(f"{'='*60}")
        
        result = self._make_request("/JSON/core/view/alerts/")
        if result and 'alerts' in result:
            alerts = result['alerts']
            
            # Count by risk level
            risk_counts = {}
            for alert in alerts:
                risk = alert.get('risk', 'Unknown')
                risk_counts[risk] = risk_counts.get(risk, 0) + 1
            
            print(f"Total Issues Found: {len(alerts)}")
            for risk, count in risk_counts.items():
                print(f"  {risk}: {count}")
            
            # High-risk summary
            high_risk = [a for a in alerts if a.get('risk') == 'High']
            if high_risk:
                print(f"\n🚨 CRITICAL: {len(high_risk)} HIGH RISK issues require immediate attention!")
                for alert in high_risk[:5]:  # Show top 5
                    print(f"  • {alert.get('name', 'Unknown')}")
        
        print(f"\nTesting completed for {len(urls)} URLs")
        print("Check ZAP GUI for detailed findings and remediation advice.")


    def get_all_sites(self):
        """Get all sites currently in the ZAP Sites tree"""
        result = self._make_request("/JSON/core/view/sites/")
        
        if result and 'sites' in result:
            sites = result['sites']
            return sites
        else:
            print("❌ Could not retrieve sites from ZAP")
            return []
    
    def display_sites_tree(self):
        """Display all sites in the ZAP Sites tree in a formatted way"""
        sites = self.get_all_sites()
        
        if not sites:
            print("📭 No sites found in the Sites tree")
            return sites
        
        print(f"\n{'='*60}")
        print("CURRENT ZAP SITES TREE")
        print(f"{'='*60}")
        print(f"Total sites discovered: {len(sites)}")
        print("-" * 40)
        
        for i, site in enumerate(sites, 1):
            print(f"{i:2d}. {site}")
        
        print("-" * 40)
        return sites

def main():
    print("ZAP Complete Security Testing")
    print("=" * 50)
    
    tester = ZAPTester(ZAP_PROXY, API_KEY)
    
    # Check connection
    if not tester.check_connection():
        return
    
    print(f"\nTesting {len(urls)} URLs...")
    print("-" * 50)
    
    tester.display_sites_tree()


    # Step 1: Add URLs to ZAP
    print("\n1. Adding URLs to ZAP...")
    successful_urls = []
    for url in urls:
        if tester.add_url(url):
            successful_urls.append(url)
        time.sleep(1)
    
    # if not successful_urls:
    #     print("❌ No URLs were successfully added. Exiting.")
    #     return
    
    # # Step 2: AJAX Spider discovery
    # print(f"\n2. Starting AJAX Spider discovery on {len(successful_urls)} URLs...")
    # for url in successful_urls:
    #     tester.start_ajax_spider(url)
    #     time.sleep(2)
    
    # # Wait for AJAX Spider to complete
    # tester.wait_for_ajax_spider()
    
    # # Step 3: Active security scanning
    # print(f"\n3. Starting Active Security Scans...")
    # for url in successful_urls:
    #     scan_id = tester.start_active_scan(url)
    #     time.sleep(3)  # Stagger scan starts
    
    # # Wait for all scans to complete
    # tester.wait_for_active_scans()
    
    # # Step 4: Generate reports
    # print("\n4. Generating Security Reports...")
    # tester.generate_reports()

if __name__ == "__main__":
    main()