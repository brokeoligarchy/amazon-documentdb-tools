#!/usr/bin/env python3

import os
import sys
import subprocess
import argparse
import re
import csv
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

def run_deployment_scanner_and_parse_csv(profile, region, start_date, end_date, temp_log_file):
    """Run deployment scanner for a specific AWS profile and return CSV data"""
    print(f"\n{'='*80}")
    print(f"Processing AWS Profile: {profile}")
    print(f"{'='*80}")
    
    # Build the command
    cmd = [
        sys.executable,  # Use current Python interpreter
        'deployment-scanner.py',
        '--region', region,
        '--log-file-name', temp_log_file
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
            
            # Read and return CSV data
            csv_file = f"{temp_log_file}.csv"
            if os.path.exists(csv_file):
                with open(csv_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                
                # Remove temporary CSV file
                os.remove(csv_file)
                
                return rows
            else:
                print(f"⚠️  Warning: CSV file not found for profile {profile}")
                return []
        else:
            print(f"❌ Error processing profile: {profile}")
            print(f"Error: {result.stderr}")
            return []
            
    except subprocess.TimeoutExpired:
        print(f"⏰ Timeout processing profile: {profile}")
        return []
    except Exception as e:
        print(f"❌ Exception processing profile {profile}: {e}")
        return []

def write_combined_csv(all_data, output_file):
    """Write all CSV data to a single file"""
    if not all_data:
        print("No data to write")
        return
    
    # Get headers from first non-empty dataset
    headers = None
    for data in all_data:
        if data and len(data) > 0:
            headers = data[0]
            break
    
    if not headers:
        print("No valid headers found")
        return
    
    # Write combined CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow(headers)
        
        # Write all data rows
        for data in all_data:
            if data and len(data) > 1:  # Skip empty datasets and headers
                for row in data[1:]:  # Skip header row
                    writer.writerow(row)
    
    print(f"✅ Combined CSV written to: {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description='Run DocumentDB Deployment Scanner for multiple AWS profiles and combine results in single CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run for all profiles in us-east-1
  python run-multi-account-scan-single-csv.py --region us-east-1 --output-file combined_analysis.csv
  
  # Run for specific profiles only
  python run-multi-account-scan-single-csv.py --region us-east-1 --output-file combined_analysis.csv --profiles prod,dev,test
  
  # Run with custom date range
  python run-multi-account-scan-single-csv.py --region us-east-1 --output-file combined_analysis.csv --start-date 20240101 --end-date 20240131
        """
    )
    
    parser.add_argument('--region', required=True, type=str, help='AWS Region')
    parser.add_argument('--start-date', required=False, type=str, help='Start date for historical usage calculations, format=YYYYMMDD')
    parser.add_argument('--end-date', required=False, type=str, help='End date for historical usage calculations, format=YYYYMMDD')
    parser.add_argument('--output-file', required=True, type=str, help='Output CSV file name for combined results')
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
    print(f"  Output file: {args.output_file}")
    if args.start_date and args.end_date:
        print(f"  Date range: {args.start_date} to {args.end_date}")
    else:
        print(f"  Date range: Last 30 days (default)")
    print(f"  Profiles to process: {profiles_to_process}")
    
    if args.dry_run:
        print(f"\nDRY RUN - Would process {len(profiles_to_process)} profiles:")
        for profile in profiles_to_process:
            print(f"  Profile: {profile}")
        print(f"  Combined results would be saved to: {args.output_file}")
        return
    
    # Process each profile
    print(f"\nStarting processing of {len(profiles_to_process)} profiles...")
    
    successful_profiles = []
    failed_profiles = []
    all_csv_data = []
    
    for i, profile in enumerate(profiles_to_process, 1):
        print(f"\n[{i}/{len(profiles_to_process)}] Processing profile: {profile}")
        
        # Create temporary log file name for this profile
        temp_log_file = f"temp_{profile}"
        
        try:
            csv_data = run_deployment_scanner_and_parse_csv(
                profile=profile,
                region=args.region,
                start_date=args.start_date,
                end_date=args.end_date,
                temp_log_file=temp_log_file
            )
            
            if csv_data:
                all_csv_data.append(csv_data)
                successful_profiles.append(profile)
            else:
                failed_profiles.append(profile)
                
        except Exception as e:
            print(f"❌ Failed to process profile {profile}: {e}")
            failed_profiles.append(profile)
    
    # Write combined CSV
    if all_csv_data:
        write_combined_csv(all_csv_data, args.output_file)
    
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
            print(f"  {profile}")
    
    if failed_profiles:
        print(f"\n❌ Failed profiles:")
        for profile in failed_profiles:
            print(f"  {profile}")
    
    print(f"\nCombined CSV file: {args.output_file}")

if __name__ == "__main__":
    main() 