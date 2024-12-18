from flask import Flask, request, jsonify
from vcenter_utils import (
    get_all_vms,
    get_vm_structure,
    get_vm_details,
    power_on_vm,
    shutdown_vm,
    restart_vm,
    power_off_vm,
)

app = Flask(__name__)

@app.route('/vms', methods=['GET'])
def list_vms():
    try:
        vms = get_all_vms()
        if vms is False:
            return jsonify({"error": "Failed to retrieve virtual machines"}), 500
        return jsonify({"vms": vms})
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500


@app.route('/vms_structure', methods=['GET'])
def list_vms_structure():
    try:
        vm_structure = get_vm_structure()
        if vm_structure is False:
            return jsonify({"error": "Failed to retrieve virtual machines"}), 500
        return jsonify({"vm_structure": vm_structure})
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500

@app.route('/vm_details', methods=['GET'])
def vm_details():
    vm_name = request.args.get('vm_name')
    if not vm_name:
        return jsonify({"error": "VM name is required"}), 400

    try:
        vm_info = get_vm_details(vm_name)
        if not vm_info:
            return jsonify({"error": f"VM '{vm_name}' not found"}), 404
        return jsonify({"vm_details": vm_info})
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500

@app.route('/vms/power', methods=['POST'])
def manage_power_endpoint():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Request must be JSON formatted"}), 400
        vm_name = data.get("vm_name")
        operation = data.get("operation")

        if not vm_name or not operation:
            return jsonify({"error": "Missing required parameters 'vm_name' or 'operation'"}), 400

        if operation == "start":
            result = power_on_vm(vm_name)
        elif operation == "shutdown":
            result = shutdown_vm(vm_name)
        elif operation == "restart":
            result = restart_vm(vm_name)
        elif operation == "poweroff":
            result = power_off_vm(vm_name)
        else:
            return jsonify({"error": f"Invalid operation '{operation}'. Supported operations: start, shutdown, restart, poweroff"}), 400

        if result:
            return jsonify({"message": f"Operation '{operation}' executed successfully for VM '{vm_name}'."}), 200
        else:
            return jsonify({"error": f"Failed to execute operation '{operation}' for VM '{vm_name}'."}), 500

    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
