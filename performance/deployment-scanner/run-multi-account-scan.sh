#!/bin/bash

# DocumentDB Deployment Scanner - Multi-Account Runner
# This script runs the deployment scanner for all AWS profiles in ~/.aws/config

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    -r, --region REGION        AWS Region (required)
    -l, --log-file-name NAME   Base log file name (required)
    -s, --start-date DATE      Start date (YYYYMMDD format)
    -e, --end-date DATE        End date (YYYYMMDD format)
    -p, --profiles LIST        Comma-separated list of profiles to process
    -d, --dry-run              Show what would be processed without running
    -h, --help                 Show this help message

Examples:
    # Run for all profiles in us-east-1
    $0 --region us-east-1 --log-file-name analysis
    
    # Run for specific profiles only
    $0 --region us-east-1 --log-file-name analysis --profiles prod,dev,test
    
    # Run with custom date range
    $0 --region us-east-1 --log-file-name analysis --start-date 20240101 --end-date 20240131
    
    # Dry run to see what would be processed
    $0 --region us-east-1 --log-file-name analysis --dry-run

EOF
}

# Function to extract profiles from ~/.aws/config
get_aws_profiles() {
    local config_file="$HOME/.aws/config"
    
    if [[ ! -f "$config_file" ]]; then
        print_error "AWS config file not found at $config_file"
        exit 1
    fi
    
    # Extract profile names from config file
    # Matches [profile name] or [default]
    local profiles=()
    
    while IFS= read -r line; do
        if [[ $line =~ ^\[(profile\s+)?([^\]]+)\]$ ]]; then
            local profile_name="${BASH_REMATCH[2]}"
            if [[ "$profile_name" != "default" ]]; then
                profiles+=("$profile_name")
            fi
        fi
    done < "$config_file"
    
    # Add default profile if it exists
    if grep -q "^\[default\]" "$config_file"; then
        profiles+=("default")
    fi
    
    echo "${profiles[@]}"
}

# Function to run deployment scanner for a profile
run_deployment_scanner() {
    local profile="$1"
    local region="$2"
    local log_file_name="$3"
    local start_date="$4"
    local end_date="$5"
    
    print_info "Processing AWS Profile: $profile"
    echo "=================================================================================="
    
    # Build command
    local cmd="python3 deployment-scanner.py --region $region --log-file-name ${log_file_name}_${profile}"
    
    # Add optional date parameters
    if [[ -n "$start_date" ]]; then
        cmd="$cmd --start-date $start_date"
    fi
    if [[ -n "$end_date" ]]; then
        cmd="$cmd --end-date $end_date"
    fi
    
    # Run with AWS_PROFILE environment variable
    if AWS_PROFILE="$profile" eval "$cmd"; then
        print_success "Successfully processed profile: $profile"
        return 0
    else
        print_error "Failed to process profile: $profile"
        return 1
    fi
}

# Parse command line arguments
REGION=""
LOG_FILE_NAME=""
START_DATE=""
END_DATE=""
PROFILES=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -l|--log-file-name)
            LOG_FILE_NAME="$2"
            shift 2
            ;;
        -s|--start-date)
            START_DATE="$2"
            shift 2
            ;;
        -e|--end-date)
            END_DATE="$2"
            shift 2
            ;;
        -p|--profiles)
            PROFILES="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$REGION" ]]; then
    print_error "Region is required"
    show_usage
    exit 1
fi

if [[ -z "$LOG_FILE_NAME" ]]; then
    print_error "Log file name is required"
    show_usage
    exit 1
fi

# Validate date arguments
if [[ -n "$START_DATE" && -z "$END_DATE" ]]; then
    print_error "Must provide --end-date when providing --start-date"
    exit 1
fi

if [[ -z "$START_DATE" && -n "$END_DATE" ]]; then
    print_error "Must provide --start-date when providing --end-date"
    exit 1
fi

# Get profiles to process
if [[ -n "$PROFILES" ]]; then
    # Use specified profiles
    IFS=',' read -ra PROFILES_ARRAY <<< "$PROFILES"
    print_info "Using specified profiles: ${PROFILES_ARRAY[*]}"
else
    # Get all profiles from config
    readarray -t PROFILES_ARRAY < <(get_aws_profiles)
    print_info "Found ${#PROFILES_ARRAY[@]} profiles in ~/.aws/config: ${PROFILES_ARRAY[*]}"
fi

if [[ ${#PROFILES_ARRAY[@]} -eq 0 ]]; then
    print_error "No profiles found to process"
    exit 1
fi

# Show configuration
echo ""
print_info "Configuration:"
echo "  Region: $REGION"
echo "  Base log file name: $LOG_FILE_NAME"
if [[ -n "$START_DATE" && -n "$END_DATE" ]]; then
    echo "  Date range: $START_DATE to $END_DATE"
else
    echo "  Date range: Last 30 days (default)"
fi
echo "  Profiles to process: ${PROFILES_ARRAY[*]}"

# Dry run mode
if [[ "$DRY_RUN" == true ]]; then
    echo ""
    print_info "DRY RUN - Would process ${#PROFILES_ARRAY[@]} profiles:"
    for profile in "${PROFILES_ARRAY[@]}"; do
        echo "  Profile: $profile -> ${LOG_FILE_NAME}_${profile}.csv"
    done
    exit 0
fi

# Process each profile
echo ""
print_info "Starting processing of ${#PROFILES_ARRAY[@]} profiles..."

successful_profiles=()
failed_profiles=()

for i in "${!PROFILES_ARRAY[@]}"; do
    profile="${PROFILES_ARRAY[$i]}"
    echo ""
    print_info "[$((i+1))/${#PROFILES_ARRAY[@]}] Processing profile: $profile"
    
    if run_deployment_scanner "$profile" "$REGION" "$LOG_FILE_NAME" "$START_DATE" "$END_DATE"; then
        successful_profiles+=("$profile")
    else
        failed_profiles+=("$profile")
    fi
done

# Summary
echo ""
echo "=================================================================================="
print_info "SCAN COMPLETED"
echo "=================================================================================="
echo "Total profiles processed: ${#PROFILES_ARRAY[@]}"
echo "Successful: ${#successful_profiles[@]}"
echo "Failed: ${#failed_profiles[@]}"

if [[ ${#successful_profiles[@]} -gt 0 ]]; then
    echo ""
    print_success "Successful profiles:"
    for profile in "${successful_profiles[@]}"; do
        echo "  $profile -> ${LOG_FILE_NAME}_${profile}.csv"
    done
fi

if [[ ${#failed_profiles[@]} -gt 0 ]]; then
    echo ""
    print_error "Failed profiles:"
    for profile in "${failed_profiles[@]}"; do
        echo "  $profile"
    done
fi

echo ""
print_info "All CSV files have been generated in the current directory." 