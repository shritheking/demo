import os
import httpx
import logging

logger = logging.getLogger(__name__)

async def start_azure_vm_if_needed():
    """
    Checks if the Azure VM is running. If it's deallocated or stopped, sends a request to start it.
    Does not raise exceptions, so it can run safely in a background task.
    """
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
    resource_group = os.getenv("AZURE_RESOURCE_GROUP")
    vm_name = os.getenv("AZURE_VM_NAME")

    if not all([tenant_id, client_id, client_secret, subscription_id, resource_group, vm_name]):
        logger.warning("Azure VM auto-start is skipped because one or more Azure credentials are not set in the environment.")
        return

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Get Token
            token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
            token_data = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://management.azure.com/.default"
            }
            token_resp = await client.post(token_url, data=token_data)
            
            if token_resp.status_code != 200:
                logger.error(f"Failed to get Azure token. Status: {token_resp.status_code}. Response: {token_resp.text}")
                return
                
            token = token_resp.json().get("access_token")
            if not token:
                logger.error("Azure token endpoint did not return an access_token.")
                return

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # 2. Check VM Status
            api_version = "2023-09-01"
            base_url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Compute/virtualMachines/{vm_name}"
            
            status_url = f"{base_url}/instanceView?api-version={api_version}"
            status_resp = await client.get(status_url, headers=headers)
            
            if status_resp.status_code != 200:
                logger.error(f"Failed to get VM status. Status: {status_resp.status_code}. Response: {status_resp.text}")
                return
                
            instance_view = status_resp.json()
            statuses = instance_view.get("statuses", [])
            
            power_state = next((s.get("code") for s in statuses if s.get("code", "").startswith("PowerState/")), None)
            
            logger.info(f"Current Azure VM PowerState: {power_state}")
            
            # 3. Start if needed
            if power_state in ["PowerState/deallocated", "PowerState/stopped", None]:
                logger.info(f"Attempting to start Azure VM {vm_name}...")
                start_url = f"{base_url}/start?api-version={api_version}"
                start_resp = await client.post(start_url, headers=headers)
                
                if start_resp.status_code in (200, 202):
                    logger.info(f"Azure VM {vm_name} start request accepted (status {start_resp.status_code}).")
                else:
                    logger.error(f"Failed to start Azure VM. Status: {start_resp.status_code}. Response: {start_resp.text}")
            elif power_state in ["PowerState/running", "PowerState/starting"]:
                logger.info(f"Azure VM {vm_name} is already running or starting. No action needed.")
            else:
                logger.warning(f"Unknown PowerState: {power_state}. Doing nothing.")

    except Exception as e:
        logger.error(f"Exception in start_azure_vm_if_needed: {e}")
