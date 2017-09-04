#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import re
import json
import msghole
import subprocess
from gi.repository import Gio
from gi.repository import GLib


class Client(msghole.EndPoint):

    def __init__(self, conn):
        super().__init__()
        self.set_iostream_and_start(conn)

    def on_error(self, excp):
        print("on_error: " + str(excp))

    def on_close(self):
        print("on_close")

    def on_notification_host_add(self, data):
        print("on_notification_host_add: " + json.dumps(data))

    def on_notification_host_change(self, data):
        print("on_notification_host_change: " + json.dumps(data))

    def on_notification_host_remove(self, data):
        print("on_notification_host_remove: " + json.dumps(data))

    def on_notification_network_list_change(self, data):
        print("on_notification_network_list_change: " + json.dumps(data))


def getGatewayIpAddress():
    ret = subprocess.check_output(["/bin/route", "-n4"]).decode("utf-8")
    # syntax: DestIp GatewayIp DestMask ... OutIntf
    m = re.search("^(0\\.0\\.0\\.0)\\s+([0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+)\\s+(0\\.0\\.0\\.0)\\s+.*\\s+(\\S+)$", ret, re.M)
    if m is None:
        return None
    return m.group(2)


def idleInvoke(func, *args):
    def _idleCallback(func, *args):
        func(*args)
        return False
    GLib.idle_add(_idleCallback, func, *args)


def getHostList(client):
    print("getHostList begin")
    client.exec_command("get-host-list",
                        return_callback=command_get_host_list_return_cb,
                        error_callback=command_get_host_list_error_cb)
    print("getHostList end")


def command_get_host_list_return_cb(data):
    print("on_command_get_host_list_return: " + json.dumps(data))
    idleInvoke(getNetworkList, client)


def command_get_host_list_error_cb(reason):
    print("on_command_get_host_list_error:" + reason)
    idleInvoke(getNetworkList, client)


def getNetworkList(client):
    print("getNetworkList begin")
    client.exec_command("get-network-list",
                        return_callback=command_get_network_list_return_cb,
                        error_callback=command_get_network_list_error_cb)
    print("getNetworkList end")


def command_get_network_list_return_cb(data):
    print("on_command_get_network_list_return: " + json.dumps(data))
    idleInvoke(setHostProperty, client)


def command_get_network_list_error_cb(reason):
    print("on_command_get_network_list_error:" + reason)
    idleInvoke(setHostProperty, client)


def setHostProperty(client):
    print("setHostProperty")
    client.send_notification("host-property-change", {
        "wakeup": True,
    })


if __name__ == "__main__":
    print("Begin")
    sc = Gio.SocketClient.new()
    sc.set_family(Gio.SocketFamily.IPV4)
    sc.set_protocol(Gio.SocketProtocol.TCP)

    print("Connect to %s:%d" % (getGatewayIpAddress(), 2222))
    conn = sc.connect_to_host(getGatewayIpAddress(), 2222)

    print("Create client")
    client = Client(conn)
    try:
        print("start mainloop")
        idleInvoke(getHostList, client)
        GLib.MainLoop().run()
    finally:
        print("Complete")
        client.close()
