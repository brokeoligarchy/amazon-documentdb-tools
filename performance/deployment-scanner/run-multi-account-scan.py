#!/usr/bin/env python3

import os
import sys
import subprocess
import argparse
import re
from pathlib import Path

def get_aws_profiles():
    """Extract AWS profile names from ~/.aws/config file"""
    config_file = Path.home() / '.aws' / 'config'
    profiles = []
    
    if not config_file.exists():
        print(f"Error: AWS config file not found at {config_file}")
        sys.exit(1)
    
    try:
        with open(config_file, 'r') as f:
            content = f.read()
            
        # Find all profile names in square brackets
        # Matches [profile name] or [default]
        profile_pattern = r'^\[(?:profile\s+)?([^\]]+)\]'
        matches = re.findall(profile_pattern, content, re.MULTILINE)
        
        for match in matches:
            if match.strip() and match.strip() != 'default':
                profiles.append(match.strip())
        
        # Add default profile if it exists
        if '[default]' in content:
            profiles.append('default')
            
        return profiles
        
    except Exception as e:
        print(f"Error reading AWS config file: {e}")
        sys.exit(1)

def run_deployment_scanner(profile, region, start_date, end_date, log_file_name):
    """Run deployment scanner for a specific AWS profile"""
    print(f"\n{'='*80}")
    print(f"Processing AWS Profile: {profile}")
    print(f"{'='*80}")
    
    # Build the command
    cmd = [
        sys.executable,  # Use current Python interpreter
        'deployment-scanner.py',
        '--region', region,
        '--log-file-name', f"{log_file_name}_{profile}"
    ]
    
    # Add optional date parameters
    if start_date:
        cmd.extend(['--start-date', start_date])
    if end_date:
        cmd.extend(['--end-date', end_date])
    
    # Set AWS_PROFILE environment variable
    env = os.environ.copy()
    env['AWS_PROFILE'] = profile
    
    try:
        # Run the deployment scanner
        result = subprocess.run(
            cmd,
            env=env,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout per profile
        )
        
        if result.returncode == 0:
            print(f"✅ Successfully processed profile: {profile}")
            if result.stdout:
                print("Output:")
                print(result.stdout)
        else:
            print(f"❌ Error processing profile: {profile}")
            print(f"Error: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print(f"⏰ Timeout processing profile: {profile}")
    except Exception as e:
        print(f"❌ Exception processing profile {profile}: {e}")

def main():
    parser = argparse.ArgumentParser(
        description='Run DocumentDB Deployment Scanner for multiple AWS profiles',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run for all profiles in us-east-1
  python run-multi-account-scan.py --region us-east-1 --log-file-name analysis
  
  # Run for specific profiles only
  python run-multi-account-scan.py --region us-east-1 --log-file-name analysis --profiles prod,dev,test
  
  # Run with custom date range
  python run-multi-account-scan.py --region us-east-1 --log-file-name analysis --start-date 20240101 --end-date 20240131
        """
    )
    
    parser.add_argument('--region', required=True, type=str, help='AWS Region')
    parser.add_argument('--start-date', required=False, type=str, help='Start date for historical usage calculations, format=YYYYMMDD')
    parser.add_argument('--end-date', required=False, type=str, help='End date for historical usage calculations, format=YYYYMMDD')
    parser.add_argument('--log-file-name', required=True, type=str, help='Base log file name for CSV output (will append profile name)')
    parser.add_argument('--profiles', required=False, type=str, help='Comma-separated list of specific profiles to process (default: all profiles)')
    parser.add_argument('--dry-run', action='store_true', help='Show which profiles would be processed without running the scanner')
    
    args = parser.parse_args()
    
    # Validate date arguments
    if (args.start_date is not None and args.end_date is None):
        print("Error: Must provide --end-date when providing --start-date")
        sys.exit(1)
    elif (args.start_date is None and args.end_date is not None):
        print("Error: Must provide --start-date when providing --end-date")
        sys.exit(1)
    
    # Get profiles to process
    if args.profiles:
        # Use specified profiles
        profiles_to_process = [p.strip() for p in args.profiles.split(',')]
        print(f"Using specified profiles: {profiles_to_process}")
    else:
        # Get all profiles from config
        all_profiles = get_aws_profiles()
        profiles_to_process = all_profiles
        print(f"Found {len(all_profiles)} profiles in ~/.aws/config: {all_profiles}")
    
    if not profiles_to_process:
        print("No profiles found to process")
        sys.exit(1)
    
    # Show what will be processed
    print(f"\nConfiguration:")
    print(f"  Region: {args.region}")
    print(f"  Base log file name: {args.log_file_name}")
    if args.start_date and args.end_date:
        print(f"  Date range: {args.start_date} to {args.end_date}")
    else:
        print(f"  Date range: Last 30 days (default)")
    print(f"  Profiles to process: {profiles_to_process}")
    
    if args.dry_run:
        print(f"\nDRY RUN - Would process {len(profiles_to_process)} profiles:")
        for profile in profiles_to_process:
            log_file = f"{args.log_file_name}_{profile}.csv"
            print(f"  Profile: {profile} -> {log_file}")
        return
    
    # Process each profile
    print(f"\nStarting processing of {len(profiles_to_process)} profiles...")
    
    successful_profiles = []
    failed_profiles = []
    
    for i, profile in enumerate(profiles_to_process, 1):
        print(f"\n[{i}/{len(profiles_to_process)}] Processing profile: {profile}")
        
        try:
            run_deployment_scanner(
                profile=profile,
                region=args.region,
                start_date=args.start_date,
                end_date=args.end_date,
                log_file_name=args.log_file_name
            )
            successful_profiles.append(profile)
        except Exception as e:
            print(f"❌ Failed to process profile {profile}: {e}")
            failed_profiles.append(profile)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"SCAN COMPLETED")
    print(f"{'='*80}")
    print(f"Total profiles processed: {len(profiles_to_process)}")
    print(f"Successful: {len(successful_profiles)}")
    print(f"Failed: {len(failed_profiles)}")
    
    if successful_profiles:
        print(f"\n✅ Successful profiles:")
        for profile in successful_profiles:
            log_file = f"{args.log_file_name}_{profile}.csv"
            print(f"  {profile} -> {log_file}")
    
    if failed_profiles:
        print(f"\n❌ Failed profiles:")
        for profile in failed_profiles:
            print(f"  {profile}")
    
    print(f"\nAll CSV files have been generated in the current directory.")

if __name__ == "__main__":
    main() 