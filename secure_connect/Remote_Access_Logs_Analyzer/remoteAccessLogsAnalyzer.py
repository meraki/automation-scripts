import requests
import getpass
import time
import pandas as pd
from termcolor import colored

pd.set_option('display.max_columns', None)  # Display all columns
pd.set_option('display.max_colwidth', None)  # Don't truncate column content
pd.set_option('display.max_rows', None)  # Display all rows
pd.set_option('display.width', None)  # Adjust display width to fit all columns

def input_epoch_time(prompt):
    """Helper function to prompt the user for an epoch time input."""
    while True:
        user_input = input(prompt)
        try:
            epoch_time = int(user_input)
            return epoch_time
        except ValueError:
            print("Invalid input. Please enter a valid epoch time.")

def save_dataframe_to_csv(df):
    """Save the given DataFrame to a CSV file with the creation date in the file name."""
    file_name = f"meraki_log_{time.strftime('%Y-%m-%d_%H-%M-%S')}.csv"
    df.to_csv(file_name, index=False)
    print(f"Data saved to {file_name}")

def main():
    """Main function to fetch and analyze Meraki remote access logs."""
    # User input for Meraki organization ID
    organization_id = input("Enter your Meraki organization ID: ")

    # User input (masked) for Meraki API key
    api_key = getpass.getpass("Enter your Meraki API key: ")

    # User input for start and end date in epoch time
    starting_after = input_epoch_time("Enter the start date in epoch time: ")
    ending_before = input_epoch_time("Enter the end date in epoch time: ")

    # Verify that the input time should be less than 30 days
    time_difference = ending_before - starting_after
    if time_difference > 30 * 24 * 60 * 60:
        print("Error: The time range should be less than 30 days.")
        return

    # Construct the API request
    base_url = 'https://api.meraki.com/api/v1'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    endpoint = f'/organizations/{organization_id}/secureConnect/remoteAccessLog'
    params = {
        't0': starting_after,
        't1': ending_before
    }

    # Send the API request and process the response
    response = requests.get(base_url + endpoint, headers=headers, params=params)
    if response.status_code == 200:
        nested_data = response.json()
        events = nested_data['data']
        df_events = pd.json_normalize(events)

        # Convert timestamp columns to datetime format
        if 'timestamp' in df_events.columns:
            df_events['timestamp'] = pd.to_datetime(df_events['timestamp'], unit='s')
        if 'connecttimestamp' in df_events.columns:
            df_events['connecttimestamp'] = df_events['connecttimestamp'].apply(
                lambda x: int(float(x)) if not pd.isna(x) else x
            )
            df_events['connecttimestamp'] = pd.to_datetime(df_events['connecttimestamp'], unit='s')

        # Color "connected" values in green and "disconnected" values in red
        if 'connectionevent' in df_events.columns:
            df_events['connectionevent'] = df_events['connectionevent'].apply(
                lambda x: colored(x, 'green') if x == 'connected' else colored(x, 'red')
            )

        # Color "win-" values in orange and "mac-" values in blue
        if 'osversion' in df_events.columns:
            df_events['osversion'] = df_events['osversion'].apply(
                lambda x: colored(x, 'yellow') if x.startswith('win-') else colored(x, 'blue')
            )
        
        # Display all columns in expanded form
        with pd.option_context('display.max_columns', None):
            print(df_events)

        # Generate statistics for selected columns
        columns = ['osversion', 'anyconnectversion', 'connectionevent', 'internalip']
        for col in columns:
            stats = df_events[col].value_counts()
            print(f"\n{col.capitalize()} Statistics:\n{stats}\n")
        
        # Save DataFrame to CSV file with creation date in the file name
        save_dataframe_to_csv(df_events)
    else:
        print(f"Error: {response.status_code}")


if __name__ == '__main__':
    main()