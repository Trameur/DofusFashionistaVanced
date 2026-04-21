#!/usr/bin/env python3
"""
Script to merge Docker default configuration with existing configuration.
Preserves existing values for SOCIAL_AUTH and other important settings.
"""

import json
import os
import sys

CONFIG_DIR = "/etc/fashionista"
CONFIG_FILE = os.path.join(CONFIG_DIR, "gen_config.json")

# Default configuration for new installations
DEFAULT_CONFIG = {
    "PASSWORD_RESET_SALT": "docker_salt_change_me",
    "EMAIL_CONFIRMATION_SALT": "docker_salt_2_change_me",
    "SECRET_KEY": "django-insecure-docker-change-me-in-production",
    "mysql_PASSWORD": "fashionista",
    "mysql_USER": "fashionista",
    "EMAIL_HOST_USER": "",
    "EMAIL_HOST_PASSWORD": "",
    "SOCIAL_AUTH_GOOGLE_OAUTH2_KEY": None,
    "SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET": None,
    "SOCIAL_AUTH_FACEBOOK_KEY": None,
    "SOCIAL_AUTH_FACEBOOK_SECRET": None,
    "DBBACKUP_S3_ACCESS_KEY": None,
    "DBBACKUP_S3_SECRET_KEY": None,
    "url_captcha_secret": None,
    "char_id_SECRET_PART_1": "docker_secret_1",
    "char_id_SECRET_PART_2": "docker_secret_2",
    "google_analytics_id": None,
    "EMAIL_USE_TLS": True,
    "EMAIL_HOST": "smtp.gmail.com",
    "EMAIL_PORT": 587,
    "TESTER_USERS_EMAILS": ["admin@localhost"],
    "SUPER_USERS_EMAILS": ["admin@localhost"]
}

def merge_configs():
    """Merge existing config with defaults, preserving non-null values."""
    
    # Ensure config directory exists
    os.makedirs(CONFIG_DIR, exist_ok=True)
    
    # Read existing config if it exists
    existing_config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                existing_config = json.load(f)
            print(f"✓ Loaded existing configuration from {CONFIG_FILE}")
        except json.JSONDecodeError as e:
            print(f"⚠ Warning: Could not parse existing config: {e}")
            print("  Will use default configuration instead")
            existing_config = {}
    else:
        print(f"ℹ No existing configuration found at {CONFIG_FILE}")
    
    # Start with defaults
    merged_config = DEFAULT_CONFIG.copy()
    
    # Merge existing config, preserving non-null values
    for key in merged_config.keys():
        if key in existing_config:
            existing_value = existing_config[key]
            # Preserve existing non-null values
            if existing_value is not None:
                merged_config[key] = existing_value
                if key.startswith('SOCIAL_AUTH') or key.endswith('_KEY') or key.endswith('_SECRET'):
                    print(f"  ✓ Preserved {key}")
            else:
                print(f"  ℹ Using default for {key} (existing was null)")
        else:
            print(f"  ℹ Using default for {key} (not in existing config)")
    
    # Add any new keys from existing config (in case of upgrades)
    for key in existing_config.keys():
        if key not in merged_config:
            merged_config[key] = existing_config[key]
            print(f"  ✓ Preserved new key {key}")
    
    # Write merged config
    with open(CONFIG_FILE, 'w') as f:
        json.dump(merged_config, f, indent=4)
    
    print(f"✓ Merged configuration written to {CONFIG_FILE}")
    
    # Verify important settings are not null
    required_keys = ['SOCIAL_AUTH_GOOGLE_OAUTH2_KEY', 'SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET']
    missing_keys = [k for k in required_keys if merged_config.get(k) is None]
    
    if missing_keys:
        print(f"\n⚠ Warning: The following OAuth keys are not configured:")
        for key in missing_keys:
            print(f"    - {key}")
        print("  Social authentication will not work until these are configured.")
    else:
        print(f"\n✓ OAuth configuration is complete!")
    
    return merged_config

if __name__ == "__main__":
    try:
        merge_configs()
    except Exception as e:
        print(f"✗ Error merging configurations: {e}", file=sys.stderr)
        sys.exit(1)
