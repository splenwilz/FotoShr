#!/usr/bin/env python3
import os
import secrets

def generate_key():
    """Generate a secure random key for Flask application."""
    return secrets.token_hex(32)

if __name__ == "__main__":
    key = generate_key()
    print("\nGenerated Secret Key:")
    print(key)
    print("\nYou can add this key to your .env file:")
    print("SECRET_KEY=" + key)
    
    # Check if .env file exists
    if os.path.exists('.env'):
        choice = input("\nDo you want to update the SECRET_KEY in the existing .env file? (y/n): ")
        if choice.lower() == 'y':
            with open('.env', 'r') as file:
                env_content = file.read()
            
            # Replace the SECRET_KEY if it exists
            if 'SECRET_KEY=' in env_content:
                import re
                env_content = re.sub(r'SECRET_KEY=.*', f'SECRET_KEY={key}', env_content)
            else:
                # Add the SECRET_KEY if it doesn't exist
                env_content += f'\nSECRET_KEY={key}'
            
            with open('.env', 'w') as file:
                file.write(env_content)
            
            print("SECRET_KEY updated in .env file.")
    else:
        print("\nNote: No .env file found. You can create one by copying .env.template.") 