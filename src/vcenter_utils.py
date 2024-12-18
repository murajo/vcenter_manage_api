from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
import ssl
import os

vcenter_host = os.getenv('VCENTER_HOST')
vcenter_user = os.getenv('VCENTER_USER')
vcenter_password = os.getenv('VCENTER_PASSWORD')
verify_ssl = os.getenv('VERIFY_SSL', 'False').lower() in ('true', '1')


def connect_to_vcenter():
    
    context = None
    if not verify_ssl:
        context = ssl._create_unverified_context()
    try:
        return SmartConnect(host=vcenter_host, user=vcenter_user, pwd=vcenter_password, sslContext=context)
    except Exception as e:
        print(f"Failed to connect to vCenter: {e}")
        return None

def get_vm_structure():
    si = connect_to_vcenter()
    if not si:
        return False
    try:
        content = si.RetrieveContent()

        def retrieve_entity(entity):
            if isinstance(entity, vim.VirtualMachine):
                return {
                    "type": "VirtualMachine",
                    "name": entity.name,
                    "power_state": entity.runtime.powerState,
                }
            elif isinstance(entity, vim.ResourcePool):
                return {
                    "type": "ResourcePool",
                    "name": entity.name,
                    "children": [retrieve_entity(child) for child in entity.resourcePool] +
                                [retrieve_entity(vm) for vm in entity.vm],
                }
            elif hasattr(entity, 'childEntity'):
                return {
                    "type": "Folder",
                    "name": entity.name,
                    "children": [retrieve_entity(child) for child in entity.childEntity],
                }
            else:
                return None

        vm_structure = []
        for datacenter in content.rootFolder.childEntity:
            vm_structure.append({
                "type": "Datacenter",
                "name": datacenter.name,
                "children": retrieve_entity(datacenter.vmFolder)
            })

        return vm_structure
    except Exception as e:
        print(f"Error retrieving VMs: {e}")
        return False
    finally:
        Disconnect(si)

def perform_vm_power_action(vm, action):
    
    power_state = vm.runtime.powerState
    actions = {
        "power_on": {
            "condition": power_state == "poweredOff",
            "operation": vm.PowerOn,
            "success": f"VM {vm.name} powered on successfully",
            "already_done": f"VM {vm.name} is already powered on"
        },
        "power_off": {
            "condition": power_state == "poweredOn",
            "operation": vm.PowerOff,
            "success": f"VM {vm.name} powered off successfully",
            "already_done": f"VM {vm.name} is already powered off"
        },
        "shutdown_guest": {
            "condition": power_state == "poweredOn",
            "operation": vm.ShutdownGuest,
            "success": f"Guest OS on VM {vm.name} is shutting down",
            "already_done": f"VM {vm.name} is not powered on"
        },
        "reboot_guest": {
            "condition": power_state == "poweredOn",
            "operation": vm.RebootGuest,
            "success": f"Guest OS on VM {vm.name} is rebooting",
            "already_done": f"VM {vm.name} is not powered on"
        },
        "reset": {
            "condition": True,
            "operation": vm.Reset,
            "success": f"VM {vm.name} has been reset",
            "already_done": None
        }
    }

    if action not in actions:
        return f"Invalid action: {action}"

    action_data = actions[action]

    if action_data["condition"]:
        try:
            action_data["operation"]()
            return action_data["success"]
        except Exception as e:
            return f"Error performing {action} on VM {vm.name}: {e}"
    else:
        return action_data["already_done"]

def get_all_vms():
    si = connect_to_vcenter()
    if not si:
        return False
    try:
        content = si.RetrieveContent()
        
        def retrieve_vms_from_entity(entity):
            vms = []
            if isinstance(entity, vim.VirtualMachine):
                vms.append({
                    "name": entity.name,
                    "power_state": entity.runtime.powerState,
                    "cpu_count": entity.config.hardware.numCPU,
                    "memory_size": entity.config.hardware.memoryMB,
                })
            elif hasattr(entity, 'childEntity'):
                for child in entity.childEntity:
                    vms.extend(retrieve_vms_from_entity(child))
            return vms

        all_vms = []
        for datacenter in content.rootFolder.childEntity:
            vms_in_datacenter = retrieve_vms_from_entity(datacenter.vmFolder)
            all_vms.extend(vms_in_datacenter)

        return all_vms
    except Exception as e:
        print(f"Error retrieving VMs: {e}")
        return False
    finally:
        Disconnect(si)

def find_vm_by_name(name, folder):
    vm = None
    for entity in folder.childEntity:
        if isinstance(entity, vim.VirtualMachine) and entity.name == name:
            vm = entity
            break
        elif hasattr(entity, 'childEntity'):
            vm = find_vm_by_name(name, entity)
            if vm:
                break
    return vm

def get_vm_details(vm_name):
    si = connect_to_vcenter()
    if not si:
        return False
    try:
        content = si.RetrieveContent()

        vm = None
        for datacenter in content.rootFolder.childEntity:
            vm = find_vm_by_name(vm_name, datacenter.vmFolder)
            if vm:
                break

        if not vm:
            print(f"VM '{vm_name}' not found.")
            return None
        
        vm_details = {
            "name": vm.name,
            "power_state": vm.runtime.powerState,
            "cpu_count": vm.config.hardware.numCPU,
            "memory_size": vm.config.hardware.memoryMB,
            "os": vm.config.guestFullName,
            "ip_address": vm.guest.ipAddress,
            "created_time": vm.config.createDate,
            "vmware_tools_status": vm.guest.toolsStatus,
            "disk_sizes": [{"disk_label": disk.deviceInfo.label, 
                                     "size_gb": disk.capacityInKB / (1024 ** 2)}
                                    for disk in vm.config.hardware.device if isinstance(disk, vim.vm.device.VirtualDisk)]
        }
        return vm_details

    except Exception as e:
        print(f"Error retrieving VM details: {e}")
        return False
    finally:
        Disconnect(si)

def power_on_vm(vm_name):
    si = connect_to_vcenter()
    if not si:
        return False
    try:
        content = si.RetrieveContent()

        vm = None
        for datacenter in content.rootFolder.childEntity:
            vm = find_vm_by_name(vm_name, datacenter.vmFolder)
            if vm:
                break

        if not vm:
            print(f"VM '{vm_name}' not found.")
            return False

        if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
            print(f"VM '{vm_name}' is already powered on.")
            return True

        task = vm.PowerOn()
        task_result = wait_for_task(task)
        if task_result:
            print(f"VM '{vm_name}' has been powered on.")
            return True
        else:
            print(f"Failed to power on VM '{vm_name}'.")
            return False

    except Exception as e:
        print(f"Error powering on VM '{vm_name}': {e}")
        return False
    finally:
        Disconnect(si)


def shutdown_vm(vm_name):
    si = connect_to_vcenter()
    if not si:
        return False
    try:
        content = si.RetrieveContent()
        vm = None
        for datacenter in content.rootFolder.childEntity:
            vm = find_vm_by_name(vm_name, datacenter.vmFolder)
            if vm:
                break

        if not vm:
            print(f"VM '{vm_name}' not found.")
            return False

        if vm.guest.toolsStatus == vim.vm.GuestToolsStatus.toolsOk:
            task = vm.ShutdownGuest()
            print(f"VM '{vm_name}' guest OS shutdown initiated.")
            return True
        else:
            print(f"VM '{vm_name}' does not have VMware Tools running or installed.")
            return False

    except Exception as e:
        print(f"Error shutting down guest OS for VM '{vm_name}': {e}")
        return False
    finally:
        Disconnect(si)


def power_off_vm(vm_name):
    si = connect_to_vcenter()
    if not si:
        return False
    try:
        content = si.RetrieveContent()
        vm = None
        for datacenter in content.rootFolder.childEntity:
            vm = find_vm_by_name(vm_name, datacenter.vmFolder)
            if vm:
                break

        if not vm:
            print(f"VM '{vm_name}' not found.")
            return False

        task = vm.PowerOff()
        task_result = wait_for_task(task)
        if task_result:
            print(f"VM '{vm_name}' has been powered off forcibly.")
            return True
        else:
            print(f"Failed to power off VM '{vm_name}'.")
            return False

    except Exception as e:
        print(f"Error powering off VM '{vm_name}': {e}")
        return False
    finally:
        Disconnect(si)


def restart_vm(vm_name):
    si = connect_to_vcenter()
    if not si:
        return False
    try:
        content = si.RetrieveContent()
        vm = None
        for datacenter in content.rootFolder.childEntity:
            vm = find_vm_by_name(vm_name, datacenter.vmFolder)
            if vm:
                break

        if not vm:
            print(f"VM '{vm_name}' not found.")
            return False

        if vm.guest.toolsStatus == vim.vm.GuestToolsStatus.toolsOk:
            task = vm.RebootGuest()
            print(f"VM '{vm_name}' guest OS restart initiated.")
            return True
        else:
            print(f"Guest tools not available. Powering off and restarting VM '{vm_name}'.")
            task = vm.PowerOff()
            wait_for_task(task)
            task = vm.PowerOn()
            task_result = wait_for_task(task)
            if task_result:
                print(f"VM '{vm_name}' has been restarted forcibly.")
                return True
            else:
                print(f"Failed to restart VM '{vm_name}'.")
                return False

    except Exception as e:
        print(f"Error restarting VM '{vm_name}': {e}")
        return False
    finally:
        Disconnect(si)


def wait_for_task(task):
    try:
        while task.info.state in [vim.TaskInfo.State.running, vim.TaskInfo.State.queued]:
            continue

        if task.info.state == vim.TaskInfo.State.success:
            return True
        else:
            print(f"Task failed with error: {task.info.error}")
            return False
    except Exception as e:
        print(f"Error waiting for task: {e}")
        return False