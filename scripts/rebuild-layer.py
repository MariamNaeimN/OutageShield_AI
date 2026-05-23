"""Rebuild Lambda layer with ALL opensearch-py dependencies."""
import subprocess, os, shutil, zipfile, boto3

REGION = 'us-east-1'
layer_dir = os.path.join(os.environ['TEMP'], 'osl2')
python_dir = os.path.join(layer_dir, 'python')

if os.path.exists(layer_dir):
    shutil.rmtree(layer_dir)
os.makedirs(python_dir)

print("Installing opensearch-py with ALL dependencies...")
subprocess.run(['pip', 'install', 'opensearch-py', 'requests', 'requests-aws4auth', '-t', python_dir, '--quiet'], check=True)

print("Creating zip...")
zip_path = os.path.join(os.environ['TEMP'], 'osl2.zip')
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(layer_dir):
        for f in files:
            fp = os.path.join(root, f)
            zf.write(fp, os.path.relpath(fp, layer_dir))

size_mb = os.path.getsize(zip_path) / (1024*1024)
print(f"Layer size: {size_mb:.1f} MB")

print("Publishing layer...")
lc = boto3.client('lambda', region_name=REGION)
with open(zip_path, 'rb') as f:
    r = lc.publish_layer_version(
        LayerName='opensearch-py',
        Description='opensearch-py with all deps v2',
        Content={'ZipFile': f.read()},
        CompatibleRuntimes=['python3.12']
    )
layer_arn = r['LayerVersionArn']
print(f"Layer: {layer_arn}")

print("Attaching to Lambdas...")
for fn in ['outageshield-detection-dev', 'outageshield-agent-actions-dev']:
    lc.update_function_configuration(FunctionName=fn, Layers=[layer_arn])
    print(f"  ✓ {fn}")

print("\n✅ Done!")
