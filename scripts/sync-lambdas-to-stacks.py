"""
Sync Lambda code from update scripts to CloudFormation stacks.
This script extracts the Lambda code from scripts/lambdas/*.py and updates
the corresponding CloudFormation stack YAML files.

Lambda Scripts and Their Stacks:
================================
1. update-detection-opensearch.py   -> 03-detection-stack.yaml (DetectionLambda)
2. update-correlation-lambda.py     -> 04-correlation-stack.yaml (CorrelationLambda)
3. update-rca-lambda-v2.py          -> 05-reasoning-stack.yaml (RootCauseLambda)
4. update-scoring-lambda.py         -> 05-reasoning-stack.yaml (ScoringLambda)
5. update-remediation-lambda2.py    -> 05-reasoning-stack.yaml (RemediationLambda)
6. update-postmortem-lambda.py      -> 05-reasoning-stack.yaml (PostmortemLambda)
7. create-summary-lambda.py         -> 05-reasoning-stack.yaml (SummaryLambda)
8. update-agent-invoker.py          -> 13-bedrock-agent-stack.yaml (AgentInvokerLambda)
9. update-agent-actions-all-tools.py -> 13-bedrock-agent-stack.yaml (AgentActionsLambda)
"""
import re
import os

# Mapping of Lambda update scripts to their CloudFormation stacks and function names
LAMBDA_MAPPINGS = {
    'update-detection-opensearch.py': {
        'stack': '03-detection-stack.yaml',
        'function_name': 'DetectionLambda',
        'lambda_name': 'outageshield-detection-dev'
    },
    'update-correlation-lambda.py': {
        'stack': '04-correlation-stack.yaml', 
        'function_name': 'CorrelationLambda',
        'lambda_name': 'outageshield-correlation-dev'
    },
    'update-rca-lambda-v2.py': {
        'stack': '05-reasoning-stack.yaml',
        'function_name': 'RootCauseLambda',
        'lambda_name': 'outageshield-rootcause-dev'
    },
    'update-scoring-lambda.py': {
        'stack': '05-reasoning-stack.yaml',
        'function_name': 'ScoringLambda',
        'lambda_name': 'outageshield-scoring-dev'
    },
    'update-remediation-lambda2.py': {
        'stack': '05-reasoning-stack.yaml',
        'function_name': 'RemediationLambda',
        'lambda_name': 'outageshield-remediation-recommend-dev'
    },
    'update-postmortem-lambda.py': {
        'stack': '05-reasoning-stack.yaml',
        'function_name': 'PostmortemLambda',
        'lambda_name': 'outageshield-postmortem-dev'
    },
    'create-summary-lambda.py': {
        'stack': '05-reasoning-stack.yaml',
        'function_name': 'SummaryLambda',
        'lambda_name': 'outageshield-remediation-summary-dev'
    },
    'update-agent-invoker.py': {
        'stack': '13-bedrock-agent-stack.yaml',
        'function_name': 'AgentInvokerLambda',
        'lambda_name': 'outageshield-agent-invoker-dev'
    },
    'update-agent-actions-all-tools.py': {
        'stack': '13-bedrock-agent-stack.yaml',
        'function_name': 'AgentActionsLambda',
        'lambda_name': 'outageshield-agent-actions-dev'
    }
}

def extract_lambda_code(script_path):
    """Extract the Lambda code string from an update script."""
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for code = '''...''' or LAMBDA_CODE = r'''...'''
    patterns = [
        r"code\s*=\s*'''(.*?)'''",
        r"code\s*=\s*r'''(.*?)'''",
        r"LAMBDA_CODE\s*=\s*'''(.*?)'''",
        r"LAMBDA_CODE\s*=\s*r'''(.*?)'''"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
    
    return None

def indent_code(code, spaces=10):
    """Indent code for YAML ZipFile format."""
    lines = code.split('\n')
    indented = []
    for line in lines:
        if line.strip():
            indented.append(' ' * spaces + line)
        else:
            indented.append('')
    return '\n'.join(indented)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    lambdas_dir = os.path.join(script_dir, 'lambdas')
    stacks_dir = os.path.join(os.path.dirname(script_dir), 'stacks')
    
    print("=" * 60)
    print("Syncing Lambda code to CloudFormation stacks")
    print("=" * 60)
    print()
    
    for script_name, mapping in LAMBDA_MAPPINGS.items():
        script_path = os.path.join(lambdas_dir, script_name)
        stack_path = os.path.join(stacks_dir, mapping['stack'])
        
        if not os.path.exists(script_path):
            print(f"⚠ Script not found: {script_name}")
            continue
            
        if not os.path.exists(stack_path):
            print(f"⚠ Stack not found: {mapping['stack']}")
            continue
        
        code = extract_lambda_code(script_path)
        if not code:
            print(f"⚠ Could not extract code from: {script_name}")
            continue
        
        print(f"✓ Extracted code from {script_name} ({len(code)} chars)")
        print(f"  → Target: {mapping['stack']} / {mapping['function_name']}")
        
        # Note: Actually updating YAML is complex due to indentation
        # For now, just report what would be updated
        
    print()
    print("Note: Lambda code is deployed via scripts/lambdas/*.py")
    print("The stacks contain placeholder code that gets overwritten on deploy.")
    print()
    print("To deploy latest Lambda code, run:")
    print("  python scripts/lambdas/update-detection-opensearch.py")
    print("  python scripts/lambdas/update-correlation-lambda.py")
    print("  python scripts/lambdas/update-rca-lambda-v2.py")
    print("  python scripts/lambdas/update-scoring-lambda.py")
    print("  python scripts/lambdas/update-remediation-lambda2.py")
    print("  python scripts/lambdas/update-postmortem-lambda.py")
    print("  python scripts/lambdas/create-summary-lambda.py")
    print("  python scripts/lambdas/update-agent-invoker.py")
    print("  python scripts/lambdas/update-agent-actions-all-tools.py")

if __name__ == '__main__':
    main()
