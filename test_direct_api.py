#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script for direct CVE API access without using the MCP server.
"""
import requests
import json
import sys

def test_cve_api():
    """Test direct access to the CVE API."""
    cve_id = "CVE-2021-44228"
    api_url = f"https://cve.circl.lu/api/cve/{cve_id}"
    
    print(f"Fetching CVE data for {cve_id} directly from {api_url}...")
    
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        
        # Parse and print the response
        data = response.json()
        
        # Extract key information
        cve_id = data.get("cveMetadata", {}).get("cveId", "Unknown")
        
        # Extract the description
        description = ""
        if "containers" in data and "cna" in data["containers"]:
            descriptions = data["containers"]["cna"].get("descriptions", [])
            if descriptions and len(descriptions) > 0:
                description = descriptions[0].get("value", "")
        
        # Print a summary
        print("\nCVE Information Summary:")
        print(f"ID: {cve_id}")
        print(f"Description: {description[:200]}...")
        
        # Print full JSON response
        print("\nFull JSON Response:")
        print(json.dumps(data, indent=2))
        
        return True
        
    except Exception as e:
        print(f"Error accessing CVE API: {e}")
        return False

if __name__ == "__main__":
    print("=== Direct CVE API Test ===")
    result = test_cve_api()
    
    if result:
        print("\nTest successful! Direct API access works correctly.")
        sys.exit(0)
    else:
        print("\nTest failed. Check error messages above.")
        sys.exit(1)