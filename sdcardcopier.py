import os
import shutil
import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from SDCardMonitor import SDCardMonitor

import sys
sys.path.append('../mqtt')
from mqtt_manager import MQTTManager

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
DESTINATION_PATH = "/mnt/drive/sdcard_backup"
MOUNT_PATH = "/mnt/sdcard"
SD_CARD_NAME = "CAMERA_SD"
MQTT_TOPIC_PREFIX = "homeassistant/sdcard"

class SDCardCopier:
    def __init__(self):
        self.sd_monitor = SDCardMonitor(SD_CARD_NAME)
        self.mqtt_manager = MQTTManager(message_callback=self.message_cb)
        self.force_stop = False
        self.unplugged = True
        self.doing_copy = False

    @contextmanager
    def copy_context(self):
        self.doing_copy = True
        try:
            yield
        finally:
            self.doing_copy = False

    def copy_content(self, source_path, destination_path):
        try:
            os.makedirs(destination_path, exist_ok=True)
            
            def copy_file(src, dst):
                if os.path.exists(dst) and os.path.getsize(src) == os.path.getsize(dst):
                    logger.info(f"Skipped (same name and size): {dst}")
                    return

                base, ext = os.path.splitext(os.path.basename(dst))
                counter = 1
                while os.path.exists(dst):
                    if os.path.getsize(src) == os.path.getsize(dst):
                        logger.info(f"Skipped (same name and size after renaming): {dst}")
                        return
                    dst = os.path.join(os.path.dirname(dst), f"{base}_{counter}{ext}")
                    counter += 1

                shutil.copy2(src, dst)
                logger.info(f"Copied: {src} -> {dst}")

            shutil.copytree(source_path, destination_path, copy_function=copy_file, dirs_exist_ok=True)
        except Exception as e:
            logger.error(f"Error copying content from {source_path} to {destination_path}: {str(e)}")

    def copy_all(self):
        with self.copy_context():
            source_images = os.path.join(MOUNT_PATH, "DCIM", "100MSDCF")
            source_videos = os.path.join(MOUNT_PATH, "PRIVATE", "M4ROOT", "CLIP")
            dest_images = os.path.join(DESTINATION_PATH, "images")
            dest_videos = os.path.join(DESTINATION_PATH, "videos")

            with ThreadPoolExecutor(max_workers=2) as executor:
                executor.submit(self.copy_content, source_images, dest_images)
                executor.submit(self.copy_content, source_videos, dest_videos)

    def message_cb(self, topic, payload):
        logger.info(f"New MQTT message received: {topic} - {payload}")
        if topic == f"{MQTT_TOPIC_PREFIX}/control/mount":
            if payload == '1' and self.sd_monitor.get_status() == "UNMOUNTED":
                self.sd_monitor.mount(MOUNT_PATH)
            elif payload == '0' and self.sd_monitor.get_status() == "MOUNTED":
                self.sd_monitor.unmount()
        elif topic == f"{MQTT_TOPIC_PREFIX}/control/copy":
            if self.sd_monitor.get_status() == "MOUNTED":            
                threading.Thread(target=self.copy_all, daemon=True).start()

    def run(self):
        logger.info("Starting SD card monitoring. Press Ctrl+C to stop.")
        try:
            while not self.force_stop:
                if self.doing_copy:
                    logger.info("SD card doing copy.")
                    self.mqtt_manager.publish_message(f"{MQTT_TOPIC_PREFIX}/status", payload="COPYING")
                elif self.sd_monitor.check_plug_status():
                    logger.info("SD card is plugged in.")
                    if self.sd_monitor.get_status() == "UNMOUNTED":
                        if self.unplugged:
                            self.sd_monitor.mount(MOUNT_PATH)
                        self.unplugged = False
                    else:
                        logger.info("SD card is MOUNTED")
                    self.mqtt_manager.publish_message(f"{MQTT_TOPIC_PREFIX}/status", payload=self.sd_monitor.get_status())
                else:
                    logger.info("SD card is NOT plugged in.")
                    self.unplugged = True
                    self.mqtt_manager.publish_message(f"{MQTT_TOPIC_PREFIX}/status", payload="UNPLUGGED")

                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped.")
            self.force_stop = True

if __name__ == "__main__":
    copier = SDCardCopier()
    copier.run()