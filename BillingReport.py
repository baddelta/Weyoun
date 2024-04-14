import json
import kazoo
from kazoo.request_objects import KazooRequest
import helperfunctions  # Ensure this module is accessible and contains necessary functions
import csv
from datetime import datetime

def billingReport(KazSess, acctId, acctName, **kwargs):
    '''
    Collects a report of normally billable items
    '''
    billableItems = {'acctName': acctName}

    # VM Transcription handling
    vmboxTranscriptionData = helperfunctions.pagedApiCallToEnd(KazSess, 'get', f'/accounts/{acctId}/vmboxes?has_key=transcribe&filter_transcribe=true')
    billableItems["vm_transcription"] = sum(1 for _ in vmboxTranscriptionData)

    # App Store data handling
    appStoreData = helperfunctions.pagedApiCallToEnd(KazSess, 'get', f'/accounts/{acctId}/apps_store')
    for app in appStoreData:
        key = "app_store_" + app['name']
        billableItems[key] = billableItems.get(key, 0) + 1

    # Phone numbers handling
    phoneNumbers = helperfunctions.pagedApiCallToEnd(KazSess, 'get', f'/accounts/{acctId}/phone_numbers')
    agNumberData = {}
    for phoneNumber, numberData in phoneNumbers.items():
        prefix = phoneNumber[0:5]
        toll_free_prefixes = ["+1800", "+1833", "+1844", "+1855", "+1866", "+1877", "+1888", "+1822"]
        if prefix in toll_free_prefixes:
            agNumberData["did_toll_free"] = agNumberData.get("did_toll_free", 0) + 1
        else:
            agNumberData["did_local"] = agNumberData.get("did_local", 0) + 1

        for feature in numberData.get("features", []):
            featureKey = f"did_feature_{feature}"
            agNumberData[featureKey] = agNumberData.get(featureKey, 0) + 1

    billableItems.update(agNumberData)

    # Generic counts of various objects
    def countObjects(objectType, segregateOn=[]):
        objectData = helperfunctions.pagedApiCallToEnd(KazSess, 'get', f'/accounts/{acctId}/{objectType}')
        objectCounts = {}
        for data in objectData:
            for subItem in segregateOn:
                subType = data.get(subItem, 'unknownType')
                fullName = f"{objectType}_{subType}"
                objectCounts[fullName] = objectCounts.get(fullName, 0) + 1
        return objectCounts

    billableItems.update(countObjects('users'))
    billableItems.update(countObjects('devices', ['device_type']))
    try:
        billableItems.update(countObjects('qubicle_queues', ['offering']))
    except Exception as e:
        print(f"Error processing qubicle queues: {str(e)}")

    try:
        billableItems.update(countObjects('qubicle_recipients', ['recipient', 'offering']))
    except Exception as e:
        print(f"Error processing qubicle recipients: {str(e)}")

    return billableItems

def runFunctionForAllDescendant(KazSess, rootAcct, includeSelf, func, **kwargs):
    '''
    Runs a function for each descendant of a root account.
    '''
    path = f'/accounts/{rootAcct}/descendants'
    allAccounts = helperfunctions.pagedApiCallToEnd(KazSess, 'get', path)
    output = {}
    if includeSelf:
        output[rootAcct] = func(KazSess, rootAcct, "Root Account", **kwargs)
    for acct in allAccounts:
        acctID = acct.get('id', '')
        if acctID:
            acctName = acct.get('name', '')
            acctResult = func(KazSess, acctID, acctName, **kwargs)
            output[acctID] = acctResult
    return output

def getKazooSession():
    api_url = input("Enter the Kazoo API URL (e.g., https://api.kazoo.com/v2): ")
    api_key = input("Enter your Kazoo API Key: ")
    return kazoo.Client(api_key=api_key, base_url=api_url)

def write_to_csv(data, filename):
    ''' Write the dictionary data to a CSV file with the given filename '''
    if not data:
        print("No data to write to CSV.")
        return

    headers = set()
    for entry in data.values():
        headers.update(entry.keys())

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=list(headers))
        writer.writeheader()
        for entry in data.values():
            writer.writerow(entry)

def main():
    KazSess = getKazooSession()
    rootAcctId = input("Enter the root account ID from which descendants will be processed: ")
    includeSelf = helperfunctions.getYesNo("Include the root account itself in the processing? (y/n): ")
    results = runFunctionForAllDescendant(KazSess, rootAcctId, includeSelf, billingReport)

    # Output results to JSON for debugging or review
    print("Results across all descendants:", json.dumps(results, indent=4))

    # Automatically save to CSV
    filename = f"billing_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    write_to_csv(results, filename)
    print(f"Results automatically saved to {filename}")

if __name__ == "__main__":
    main()
