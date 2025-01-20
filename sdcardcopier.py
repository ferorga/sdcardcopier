import os
import shutil
import time
import threading

from SDCardMonitor import SDCardMonitor

import sys
sys.path.append('../mqtt')
from mqtt_manager import MQTTManager

def copy_content(source_path, destination_path):
    """
    Copies content from the source path to the destination path.

    Args:
        source_path (str): Path of the source directory (SD card mount point).
        destination_path (str): Path of the destination directory.

    Returns:
        None
    """
    for root, dirs, files in os.walk(source_path):
        relative_path = os.path.relpath(root, source_path)
        target_dir = os.path.join(destination_path, relative_path)

        # Create the target directory if it doesn't exist
        os.makedirs(target_dir, exist_ok=True)

        for file in files:
            source_file = os.path.join(root, file)
            target_file = os.path.join(target_dir, file)

            # If the file exists, compare the size
            if os.path.exists(target_file):
                source_size = os.path.getsize(source_file)
                target_size = os.path.getsize(target_file)

                if source_size == target_size:
                    print(f"Skipped (same name and size): {target_file}")
                    continue
                else:
                    # Handle naming conflicts by appending an incremented suffix
                    base, ext = os.path.splitext(file)
                    counter = 2

                    # Check if the file exists and its size until a match is found or the file doesn't exist
                    while os.path.exists(target_file):
                        target_size = os.path.getsize(target_file)

                        if source_size == target_size:
                            print(f"Skipped (same name and size after renaming): {target_file}")
                            break

                        target_file = os.path.join(
                            target_dir, f"{base}_{counter}{ext}")
                        counter += 1
            # Copy the file if it wasn't skipped
            shutil.copy2(source_file, target_file)
            print(f"Copied: {source_file} -> {target_file}")    

def copy_all():
    global doing_copy

    doing_copy = True

    copy_content(os.path.join(mount_path, "DCIM/100MSDCF"), os.path.join(destination_path, "images"))
    copy_content(os.path.join(mount_path, "PRIVATE/M4ROOT/CLIP"), os.path.join(destination_path, "videos"))

    doing_copy = False

def message_cb(topic, payload):    
    print("New MQTT message received!")
    if topic == "homeassistant/sdcard/control/mount":
        if payload == '1' and sd_monitor.get_status() == "UNMOUNTED":
            sd_monitor.mount(mount_path)
        elif payload == '0' and sd_monitor.get_status() == "MOUNTED":
            sd_monitor.unmount()
    elif topic == "homeassistant/sdcard/control/copy":
        if sd_monitor.get_status() == "MOUNTED":            
            copy_thread = threading.Thread(target=copy_all)   
            copy_thread.start()                     

if __name__ == "__main__":
    # Create an instance of SDCardMonitor
    sd_monitor = SDCardMonitor("CAMERA_SD")

    destination_path = "/mnt/drive/sdcard_backup"  # Change this to your desired destination
    mount_path = "/mnt/sdcard"

    force_stop = False
    unplugged = True
    doing_copy = False

    mqtt_manager = MQTTManager(message_callback=message_cb)

    print("Starting SD card monitoring. Press Ctrl+C to stop.")
    try:
        while not force_stop:
            if doing_copy:
                print("SD card doing copy.")
                mqtt_manager.publish_message("homeassistant/sdcard/status", payload="COPYING")
            elif sd_monitor.check_plug_status():
                print("SD card is plugged in.")
                if sd_monitor.get_status() == "UNMOUNTED":
                    if unplugged:
                        sd_monitor.mount(mount_path)
                    unplugged = False
                else:
                    print("SD card is MOUNTED")
                mqtt_manager.publish_message("homeassistant/sdcard/status", payload=sd_monitor.get_status())
            else:
                print("SD card it NOT plugged in.")
                unplugged = True
                mqtt_manager.publish_message("homeassistant/sdcard/status", payload="UNPLUGGED")

            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Monitoring stopped.")
        force_stop = True
