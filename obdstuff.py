import serial
import time
import serial.tools.list_ports
import threading

# Utility functions
def hex_to_decimal(hex_str):
    return int(hex_str, 16)

def parse_obd_response(pid, response):
    """
    Parse the response based on the PID and return the interpreted data.
    """
    result = {
        "pid": pid,
        "raw_response": response,
        "value": None,
        "error": None,
    }

    try:
        response = response.strip().replace("\r", "").replace("\n", "")
        parts = response.split()

        if pid == '010C':  # Engine RPM
            if len(parts) >= 4 and parts[1] == '0C':
                A = hex_to_decimal(parts[2])
                B = hex_to_decimal(parts[3])
                rpm = ((A * 256) + B) / 4
                result["value"] = f"{rpm} RPM"
            else:
                result["error"] = "No valid RPM data."
        
        elif pid == '010D':  # Vehicle Speed
            if len(parts) >= 3 and parts[1] == '0D':
                speed = hex_to_decimal(parts[2])
                result["value"] = f"{speed} km/h"
            else:
                result["error"] = "No valid speed data."
        
        elif pid == '0105':  # Coolant Temperature
            if len(parts) >= 3 and parts[1] == '05':
                temp = hex_to_decimal(parts[2]) - 40  # Adjusted for OBD-II encoding
                result["value"] = f"{temp} °C"
            else:
                result["error"] = "No valid coolant temperature data."
        
        # Add more PIDs here as needed
        
        else:
            result["error"] = f"Unsupported PID: {pid}"
    
    except Exception as e:
        result["error"] = f"Error parsing PID {pid}: {e}"
    
    return result

# Connection manager class
class OBDConnectionManager:
    def __init__(self, baud_rate=9600, timeout=1):
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.obd_port = None
        self.serial_connection = None
        self.keep_running = True
        self.lock = threading.Lock()
        self.connection_thread = threading.Thread(target=self._maintain_connection)
        self.connection_thread.start()

    def _maintain_connection(self):
        while self.keep_running:
            if self.serial_connection is None or not self.serial_connection.is_open:
                print("Attempting to reconnect...")
                self.obd_port = find_obd_port_multithreaded(self.baud_rate, self.timeout)
                if self.obd_port:
                    try:
                        self.serial_connection = serial.Serial(self.obd_port, self.baud_rate, timeout=self.timeout)
                        print(f"Reconnected to OBD-II adapter on port {self.obd_port}")
                    except serial.SerialException as e:
                        print(f"Failed to reconnect: {e}")
                        self.serial_connection = None
                else:
                    print("No OBD-II adapter found.")
            time.sleep(5)

    def send_command(self, command):
        with self.lock:
            if self.serial_connection and self.serial_connection.is_open:
                try:
                    self.serial_connection.write(f"{command}\r".encode())
                    time.sleep(1)
                    response = self.serial_connection.read_all().decode('utf-8', errors='ignore').strip()
                    return response
                except Exception as e:
                    print(f"Error sending command: {e}")
                    self.serial_connection = None  # Force reconnection
            return "No response - connection not available."

    def close(self):
        self.keep_running = False
        if self.connection_thread.is_alive():
            self.connection_thread.join()
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()

# Multithreaded OBD-II port finder
def test_port(port, baud_rate, timeout, result, stop_event):
    if stop_event.is_set():
        return
    try:
        ser = serial.Serial(port.device, baud_rate, timeout=timeout)
        print(f"Testing port: {port.device}")
        ser.write(b'ATZ\r')
        time.sleep(1)
        response = ser.read_all().decode('utf-8', errors='ignore').strip()
        if response and not stop_event.is_set():
            print(f"OBD-II adapter found on port: {port.device}")
            result["found"] = port.device
            stop_event.set()
        ser.close()
    except Exception:
        pass

def find_obd_port_multithreaded(baud_rate=9600, timeout=1):
    ports = serial.tools.list_ports.comports()
    threads = []
    result = {"found": None}
    stop_event = threading.Event()
    for port in ports:
        thread = threading.Thread(target=test_port, args=(port, baud_rate, timeout, result, stop_event))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    return result["found"]

# Main function
def main():
    manager = OBDConnectionManager()

    try:
        # List of PIDs to query
        pids = ['010C', '010D', '0105']  # RPM, Speed, Coolant Temp

        while True:
            for pid in pids:
                response = manager.send_command(pid)
                parsed_data = parse_obd_response(pid, response)

                print(f"PID: {parsed_data['pid']}")
                print(f"Raw Response: {parsed_data['raw_response']}")
                print(f"Value: {parsed_data['value']}")
                if parsed_data["error"]:
                    print(f"Error: {parsed_data['error']}")

            time.sleep(2)  # Adjust query interval as needed
    except KeyboardInterrupt:
        print("Exiting program...")
    finally:
        manager.close()

if __name__ == "__main__":
    main()
