"""
Test and update ServiceNow credentials
"""

import boto3
import json
import base64
import urllib.request
import urllib.error
import getpass

ssm = boto3.client('ssm', region_name='us-east-1')

SERVICENOW_INSTANCE = 'dev252089.service-now.com'

print("=" * 60)
print("SERVICENOW CREDENTIALS TEST")
print("=" * 60)
print(f"\nInstance: https://{SERVICENOW_INSTANCE}")

# Get current stored credentials
print("\n1. Checking stored credentials...")
try:
    stored_user = ssm.get_parameter(Name='/outageshield/servicenow/username', WithDecryption=True)['Parameter']['Value']
    print(f"   Stored username: {stored_user}")
except:
    stored_user = None
    print("   No username stored")

# Ask for credentials
print("\n2. Enter your ServiceNow credentials:")
print("   (Default username for PDI is usually 'admin')")
username = input(f"   Username [{stored_user or 'admin'}]: ").strip() or stored_user or 'admin'
password = getpass.getpass("   Password: ")

if not password:
    print("   ❌ Password is required")
    exit(1)

# Test the credentials
print("\n3. Testing credentials...")
url = f"https://{SERVICENOW_INSTANCE}/api/now/table/sys_user?sysparm_limit=1"
credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

req = urllib.request.Request(url)
req.add_header('Authorization', f'Basic {credentials}')
req.add_header('Content-Type', 'application/json')
req.add_header('Accept', 'application/json')

try:
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode())
        print("   ✅ Credentials are valid!")
        
        # Store the working credentials
        print("\n4. Storing credentials in AWS SSM...")
        ssm.put_parameter(
            Name='/outageshield/servicenow/instance',
            Value=SERVICENOW_INSTANCE,
            Type='String',
            Overwrite=True
        )
        ssm.put_parameter(
            Name='/outageshield/servicenow/username',
            Value=username,
            Type='SecureString',
            Overwrite=True
        )
        ssm.put_parameter(
            Name='/outageshield/servicenow/password',
            Value=password,
            Type='SecureString',
            Overwrite=True
        )
        print("   ✅ Credentials stored successfully!")
        print("\n   Now run: python scripts/configure-servicenow-instance.py")
        
except urllib.error.HTTPError as e:
    error_body = e.read().decode() if e.fp else ''
    print(f"   ❌ HTTP {e.code}: {error_body[:200]}")
    
    if e.code == 401:
        print("\n   Authentication failed. Possible issues:")
        print("   - Wrong username or password")
        print("   - Account may be locked")
        print("   - PDI may have hibernated (wake it up first)")
        print(f"\n   Try logging in manually at: https://{SERVICENOW_INSTANCE}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
