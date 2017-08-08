#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import json
import signal
import socket
import logging
import pyroute2
import msghole
from gi.repository import Gio
from . import util


def get_plugin_list():
    return ["advhost"]


def get_plugin(name):
    if name == "advhost":
        return _PluginObject()
    else:
        assert False


class _PluginObject:

    def init2(self, cfg, tmpDir, varDir, data):
        self.param = data
        self.logger = logging.getLogger(self.__module__ + "." + self.__class__.__name__)

    def dispose(self):
        pass

    def manager_initialized(self, name):
        if name == "apiserver":
            self.param.managers[name].register_endpoint_factory("advhost", ApiServerEndPointFactory(self))


class ApiServerEndPointFactory:

    def __init__(self, pObj):
        self.pObj = pObj

    def new_endpoint(self, local_ip, local_port, peer_ip, peer_port, sproc):
        return ApiServerEndPoint(self.pObj, peer_ip, sproc)


class ApiServerEndPoint:

    def __init__(self, pObj, peer_ip, sproc):
        self.pObj = pObj
        self.peer_ip = peer_ip
        self.sproc = sproc

    def init2(self, data):
        # send reply
        data2 = dict()
        data2["network-list"] = []
        data2["client-list"] = []
        return data2

    def close(self):
        pass

    def on_notification_network_list_change(self, data):
        pass

    def on_notification_client_add(self, data):
        pass

    def on_notification_client_change(self, data):
        pass

    def on_notification_client_remove(self, data):
        pass

    def on_command_wakeup(self, data, return_callback, error_callback):
        pass
