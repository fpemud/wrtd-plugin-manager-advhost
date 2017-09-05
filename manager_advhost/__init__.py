#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import logging
import msghole
import ipaddress
from gi.repository import Gio


def get_plugin_list():
    return ["advhost"]


def get_plugin(name):
    if name == "advhost":
        return _PluginObject()
    else:
        assert False


class _PluginObject:

    @property
    def init_after(self):
        return ["cascade"]

    def init2(self, cfg, tmpDir, varDir, data):
        self.param = data
        self.logger = logging.getLogger(self.__module__ + "." + self.__class__.__name__)

        self.apiPort = 2222
        self.apiServer = None

        self.clientList = dict()                   # ip-data-dict

        self.downstreamRouterIpList = []

        self.cascadeRouter = dict()                # dict<peer-uuid, list<router-id>>
        self.cascadeLanPrefixListDict = dict()     # dict<router-id, list<lan-prefix>>
        self.cascadeClientListDict = dict()        # dict<router-id, client-ip-data-dict>

        try:
            self.apiServer = _ApiServer(self)
            self.logger.info("ADVHOST-API server started.")
        except:
            self.dispose()
            raise

    def dispose(self):
        if self.apiServer is not None:
            self.apiServer.close()
            self.logger.info("ADVHOST-API server stopped.")

    def get_router_info(self):
        return dict()

    def on_client_add(self, source_id, ip_data_dict):
        assert len(ip_data_dict) > 0
        self.clientList.update(ip_data_dict)
        for sproc in self.apiServer.sprocList:
            sproc.send_notification("host-add", ip_data_dict)

    def on_client_change(self, source_id, ip_data_dict):
        assert len(ip_data_dict) > 0
        self.clientList.update(ip_data_dict)
        for sproc in self.apiServer.sprocList:
            sproc.send_notification("host-change", ip_data_dict)

    def on_client_remove(self, source_id, ip_list):
        assert len(ip_list) > 0

        for ip in ip_list:
            del self.clientList[ip]
        for sproc in self.apiServer.sprocList:
            if sproc.peer_ip in ip_list:
                sproc.close()

        for sproc in self.apiServer.sprocList:
            sproc.send_notification("host-remove", ip_list)

    def on_cascade_upstream_up(self, api_client, data):
        self._cascadePeerUp(api_client.peer_uuid, data)

    def on_cascade_upstream_down(self, api_client):
        self._cascadePeerDown(api_client.peer_uuid)

    def on_cascade_upstream_router_add(self, api_client, data):
        self._cascadePeerRouterAdd(api_client.peer_uuid, data)

    def on_cascade_upstream_router_remove(self, api_client, data):
        self._cascadePeerRouterRemove(api_client.peer_uuid, data)

    def on_cascade_upstream_router_lan_prefix_list_change(self, api_client, data):
        self._cascadePeerRouterLanPrefixListChange(api_client.peer_uuid, data)

    def on_cascade_upstream_router_client_add(self, api_client, data):
        self._cascadePeerRouterClientAdd(api_client.peer_uuid, data)

    def on_cascade_upstream_router_client_change(self, api_client, data):
        self._cascadePeerRouterClientChange(api_client.peer_uuid, data)

    def on_cascade_upstream_router_client_remove(self, api_client, data):
        self._cascadePeerRouterClientRemove(api_client.peer_uuid, data)

    def on_cascade_downstream_up(self, sproc, data):
        # check
        for sproc2 in self.apiServer.sprocList:
            if sproc2.peer_ip == sproc.peer_ip:
                raise msghole.BusinessException("no connection is allowed between routers")

        # process
        self.downstreamRouterIpList.append(sproc.peer_ip)
        self._cascadePeerUp(sproc.peer_uuid, data)

    def on_cascade_downstream_down(self, sproc):
        self._cascadePeerDown(sproc.peer_uuid)
        self.downstreamRouterIpList.remove(sproc.peer_ip)

    def on_cascade_downstream_router_add(self, sproc, data):
        self._cascadePeerRouterAdd(sproc.peer_uuid, data)

    def on_cascade_downstream_router_remove(self, sproc, data):
        self._cascadePeerRouterRemove(sproc.peer_uuid, data)

    def on_cascade_downstream_router_lan_prefix_list_change(self, sproc, data):
        self._cascadePeerRouterLanPrefixListChange(sproc.peer_uuid, data)

    def on_cascade_downstream_router_client_add(self, sproc, data):
        self._cascadePeerRouterClientAdd(sproc.peer_uuid, data)

    def on_cascade_downstream_router_client_change(self, sproc, data):
        self._cascadePeerRouterClientChange(sproc.peer_uuid, data)

    def on_cascade_downstream_router_client_remove(self, sproc, data):
        self._cascadePeerRouterClientRemove(sproc.peer_uuid, data)

    def _cascadePeerUp(self, peer_uuid, data):
        self.cascadeRouter[peer_uuid] = []
        self._cascadePeerRouterAdd(peer_uuid, data)

    def _cascadePeerDown(self, peer_uuid):
        self._cascadePeerRouterRemove(peer_uuid, self.cascadeRouter[peer_uuid])
        del self.cascadeRouter[peer_uuid]

    def _cascadePeerRouterAdd(self, peer_uuid, data):
        for router_id in data:
            self.cascadeRouter[peer_uuid].append(router_id)
        self._cascadePeerRouterLanPrefixListChange(peer_uuid, data)
        self._cascadePeerRouterClientAdd(peer_uuid, data)

    def _cascadePeerRouterRemove(self, peer_uuid, data):
        # update router id list
        for router_id in data:
            self.cascadeRouter[peer_uuid].remove(router_id)

        # update lan prefix list
        bLanPrefixListChanged = False
        for router_id in data:
            if router_id not in self.cascadeLanPrefixListDict:
                continue
            del self.cascadeLanPrefixListDict[router_id]
            bLanPrefixListChanged = True

        # update client list
        clientData = []
        for router_id in data:
            if router_id not in self.cascadeClientListDict:
                continue
            clientData += list(self.cascadeClientListDict[router_id].keys())
            del self.cascadeClientListDict[router_id]

        # send notification
        if bLanPrefixListChanged:
            for sproc in self.apiServer.sprocList:
                sproc.send_notification("network-list-change", self._getNetworkList())
        if clientData != []:
            for sproc in self.apiServer.sprocList:
                sproc.send_notification("host-remove", clientData)

    def _cascadePeerRouterLanPrefixListChange(self, peer_uuid, data):
        # update lan prefix list
        bChanged = False
        for router_id, data2 in data.items():
            if "lan-prefix-list" not in data2:
                continue                            # may be called from on_cascade_upstream_router_add
            if router_id in self.cascadeClientListDict:
                if set(self.cascadeClientListDict[router_id]) == set(data2["lan-prefix-list"]):
                    continue
            self.cascadeLanPrefixListDict[router_id] = data2["lan-prefix-list"]
            bChanged = True

        # send notification
        if bChanged:
            for sproc in self.apiServer.sprocList:
                sproc.send_notification("network-list-change", self._getNetworkList())

    def _cascadePeerRouterClientAdd(self, peer_uuid, data):
        # update client list, get notification data
        data3 = dict()
        for router_id, data2 in data.items():
            if "client-list" not in data2:
                continue                            # may be called from on_cascade_upstream_router_add
            if router_id not in self.cascadeClientListDict:
                self.cascadeClientListDict[router_id] = dict()
            self.cascadeClientListDict[router_id].update(data2["client-list"])
            data3.update(data2)

        # send notification
        if len(data3) > 0:
            for sproc in self.apiServer.sprocList:
                sproc.send_notification("host-add", data3)

    def _cascadePeerRouterClientChange(self, peer_uuid, data):
        assert len(data) > 0

        # update client list, get notification data
        data3 = dict()
        for router_id, data2 in data.items():
            self.cascadeClientListDict[router_id].update(data2["client-list"])
            data3.update(data2["client-list"])

        # send notification
        for sproc in self.apiServer.sprocList:
            sproc.send_notification("host-change", data3)

    def _cascadePeerRouterClientRemove(self, peer_uuid, data):
        assert len(data) > 0

        # update client list, get notification data
        data3 = []
        for router_id, data2 in data.items():
            for ip in data2["client-list"]:
                del self.cascadeClientListDict[ip]
            data3 += data2["client-list"]

        # send notification
        for sproc in self.apiServer.sprocList:
            sproc.send_notification("host-remove", data3)

    def _getNetworkList(self):
        ret = set()
        for bridge in [self.param.managers["lan"].defaultBridge] + [x.get_bridge() for x in self.param.managers["lan"].vpnsPluginList]:
            s = bridge.get_prefix()[0] + "/" + bridge.get_prefix()[1]
            ret.add(s)
        for networkList in self.cascadeLanPrefixListDict.values():
            ret |= set(networkList)
        return list(ret)

    def _getHostList(self):
        ret = self.clientList.copy()
        for clientList in self.cascadeClientListDict.values():
            ret.update(clientList)
        return ret


class _ApiServer:

    def __init__(self, pObj):
        self.pObj = pObj
        self.param = pObj.param
        self.logger = pObj.logger

        self.serverListener = Gio.SocketListener.new()
        addr = Gio.InetSocketAddress.new_from_string("0.0.0.0", self.pObj.apiPort)
        self.serverListener.add_address(addr, Gio.SocketType.STREAM, Gio.SocketProtocol.TCP)
        self.serverListener.accept_async(None, self._on_accept)

        self.sprocList = []

    def close(self):
        for sproc in self.sprocList:
            sproc.close()
        self.serverListener.close()

    def _on_accept(self, source_object, res):
        conn, dummy = source_object.accept_finish(res)
        peer_ip = conn.get_remote_address().get_address().to_string()
        peer_port = conn.get_remote_address().get_port()

        if peer_ip in self.pObj.downstreamRouterIpList:
            self.logger.error("Advanced host \"%s:%d\" rejected, no connection is allowed between routers." % (peer_ip, peer_port))
            conn.close()
            return

        bFound = False
        bridgeList = [self.param.managers["lan"].defaultBridge] + [x.get_bridge() for x in self.param.managers["lan"].vpnsPluginList]
        for bridge in bridgeList:
            netobj = ipaddress.IPv4Network(bridge.get_prefix()[0] + "/" + bridge.get_prefix()[1])
            if ipaddress.IPv4Address(peer_ip) in netobj:
                bFound = True
                break
        if not bFound:
            self.logger.error("Advanced host \"%s:%d\" rejected, invalid IP address." % (peer_ip, peer_port))
            conn.close()
            return

        self.sprocList.append(_ApiServerProcessor(self.pObj, self, conn))
        self.logger.info("Advanced host \"%s:%d\" connected." % (peer_ip, peer_port))

        self.serverListener.accept_async(None, self._on_accept)


class _ApiServerProcessor(msghole.EndPoint):

    def __init__(self, pObj, serverObj, conn):
        super().__init__()

        self.pObj = pObj
        self.param = pObj.param
        self.logger = pObj.logger

        self.serverObj = serverObj

        self.peer_ip = conn.get_remote_address().get_address().to_string()
        self.peer_port = conn.get_remote_address().get_port()

        super().set_iostream_and_start(conn)
        if self._is_local_peer():
            self.param.managers["lan"].set_property(self._source(), dict())
        else:
            self.param.managers["lan"].set_client_property(self.peer_ip, self._source(), dict())

    def on_error(self, e):
        if isinstance(e, msghole.PeerCloseError):   # we think this is normal case
            return
        self.logger.error("Error occured in server processor for advanced host \"%s:%d\"" % (self.peer_ip, self.peer_port), exc_info=True)

    def on_close(self):
        self.serverObj.sprocList.remove(self)
        self.logger.info("Advanced host \"%s:%d\" disconnected." % (self.peer_ip, self.peer_port))
        if self._is_local_peer():
            self.param.managers["lan"].remove_property(self._source())
        else:
            self.param.managers["lan"].remove_client_property(self.peer_ip, self._source())

    def on_command_get_network_list(self, data, return_callback, error_callback):
        self.logger.debug("Command \"get-network-list\" received from \"%s:%d\"." % (self.peer_ip, self.peer_port))
        ret = self.pObj._getNetworkList()
        self.logger.debug("Command execution completed.")
        return_callback(ret)

    def on_command_get_host_list(self, data, return_callback, error_callback):
        self.logger.debug("Command \"get-host-list\" received from \"%s:%d\"." % (self.peer_ip, self.peer_port))
        ret = self.pObj._getHostList()
        self.logger.debug("Command execution completed.")
        return_callback(ret)

    def on_notification_host_property_change(self, data):
        self.logger.debug("Notification \"host-property-change\" received from \"%s:%d\"." % (self.peer_ip, self.peer_port))
        if self._is_local_peer():
            self.param.managers["lan"].set_property(self._source(), data)
        else:
            self.param.managers["lan"].set_client_property(self.peer_ip, self._source(), data)
        self.logger.debug("Notification process completed.")

    def _source(self):
        return "port%d" % (self.peer_port)

    def _is_local_peer(self):
        return self.peer_ip.startswith("127.")
