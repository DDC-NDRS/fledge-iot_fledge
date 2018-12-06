# -*- coding: utf-8 -*-

# FOGLAMP_BEGIN
# See: http://foglamp.readthedocs.io/
# FOGLAMP_END


import asyncio
import uuid
import pytest
import json
from aiohttp import web
from unittest.mock import MagicMock, call

from foglamp.services.core import routes
from foglamp.services.core import connect
from foglamp.common.service_record import ServiceRecord
from foglamp.common.configuration_manager import ConfigurationManager
from foglamp.services.core.service_registry.service_registry import ServiceRegistry
from foglamp.services.core.service_registry import exceptions as service_registry_exceptions
from foglamp.services.core.api import notification
from foglamp.common.audit_logger import AuditLogger

__author__ = "Amarendra K Sinha"
__copyright__ = "Copyright (c) 2017 Dianomic Systems"
__license__ = "Apache 2.0"
__version__ = "${VERSION}"

mock_registry = [ServiceRecord(uuid.uuid4(), "Notifications", "Notification", "http", "localhost", "8118", "8118")]
rule_config = {
    "threshold": {
        "plugin": {
            "description": "The accepted tolerance",
            "default": "threshold",
            "value": "threshold",
            "type": "string"
        },
        "tolerance": {
            "description": "The accepted tolerance",
            "default": "4",
            "value": "4",
            "type": "integer"
        },
        "window": {
            "description": "The window to perform rule evaluation over in minutes",
            "default": "60",
            "value": "60",
            "type": "integer"
        },
        "trigger": {
            "description": "Temparature threshold value",
            "default": "40",
            "value": "40",
            "type": "integer"
        },
        "asset": {
            "description": "The asset the notification is defined against",
            "default": "temperature",
            "value": "temperature",
            "type": "string"
        }
    }
}

delivery_config = {"email": {
    "plugin": {
        "description": "Email",
        "default": "email",
        "value": "email",
        "type": "string"
    },
    "server": {
        "description": "The smtp server",
        "default": "smtp",
        "value": "smtp",
        "type": "string"
    },
    "from": {
        "description": "The from address to use in the email",
        "default": "foglamp",
        "value": "foglamp",
        "type": "string"
    },
    "to": {
        "description": "The address to send the notification to",
        "default": "test",
        "value": "test",
        "type": "string"
    }
},
    "sms": {
        "plugin": {
            "description": "SMS",
            "default": "sms",
            "value": "sms",
            "type": "string"
        },
        "number": {
            "description": "The phone number to call",
            "default": "07812 343830",
            "value": "07812 343830",
            "type": "string",
        }
    }
}

NOTIFICATION_TYPE = notification.NOTIFICATION_TYPE
notification_config = {
    "name": {
        "description": "The name of this notification",
        "type": "string",
        "default": "Test Notification",
        "value": "Test Notification",
    },
    "description": {
        "description": "Description of this notification",
        "type": "string",
        "default": "description",
        "value": "description",
    },
    "rule": {
        "description": "Rule to evaluate",
        "type": "string",
        "default": "threshold",
        "value": "threshold",
    },
    "channel": {
        "description": "Channel to send alert on",
        "type": "string",
        "default": "email",
        "value": "email",
    },
    "notification_type": {
        "description": "Type of notification",
        "type": "enumeration",
        "options": NOTIFICATION_TYPE,
        "default": "one shot",
        "value": "one shot",
    },
    "enable": {
        "description": "Enabled",
        "type": "boolean",
        "default": "true",
        "value": "true",
    }
}


@asyncio.coroutine
def mock_get_url(get_url):
    if get_url.endswith("/foglamp/notification/rules"):
        return json.dumps(rule_config)
    if get_url.endswith("/foglamp/notification/delivery"):
        return json.dumps(delivery_config)
    if get_url.endswith("/plugin"):
        return json.dumps({'rules': rule_config, 'delivery': delivery_config})
    if get_url.endswith("/foglamp/notification"):
        return json.dumps(notification_config)
    if get_url.endswith("/foglamp/notification/Test Notification"):
        notif = {
            "name": notification_config['name']['value'],
            "description": notification_config['description']['value'],
            "rule": notification_config['rule']['value'],
            "ruleConfig": rule_config[notification_config['rule']['value']],
            "channel": notification_config['channel']['value'],
            "deliveryConfig": delivery_config[notification_config['channel']['value']],
            "notificationType": notification_config['notification_type']['value'],
            "enable": notification_config['enable']['value'],
        }
        return json.dumps(notif)


@asyncio.coroutine
def mock_post_url(post_url):
    if post_url.endswith("/foglamp/notification/Test Notification"):
        return json.dumps({"result": "OK"})
    if post_url.endswith("/foglamp/notification/Test Notification/rule/threshold"):
        return json.dumps({"result": "OK"})
    if post_url.endswith("/foglamp/notification/Test Notification/delivery/email"):
        return json.dumps({"result": "OK"})


@asyncio.coroutine
def mock_read_category_val(key):
    if key.endswith("ruleTest Notification"):
        return rule_config[notification_config['rule']['value']]
    if key.endswith("deliveryTest Notification"):
        return delivery_config[notification_config['channel']['value']]
    if key.endswith("Test Notification"):
        return notification_config
    return ""


@asyncio.coroutine
def mock_read_all_child_category_names():
    return [{
        "parent": "Notifications",
        "child": "Test Notification",
    }]


@asyncio.coroutine
def mock_create_category():
    return ""


@asyncio.coroutine
def mock_update_category():
    return ""


@asyncio.coroutine
def mock_create_child_category():
    return ""


@pytest.allure.feature("unit")
@pytest.allure.story("core", "api", "notification")
class TestNotification:
    @pytest.fixture
    def client(self, loop, test_client):
        app = web.Application(loop=loop)
        routes.setup(app)
        return loop.run_until_complete(test_client(app))

    async def test_get_plugin(self, mocker, client):
        rules_and_delivery = {'rules': rule_config, 'delivery': delivery_config}
        mocker.patch.object(ServiceRegistry, 'get', return_value=mock_registry)
        mocker.patch.object(notification, '_hit_get_url', side_effect=[mock_get_url("/foglamp/notification/rules"),
                                                                       mock_get_url("/foglamp/notification/delivery")])

        resp = await client.get('/foglamp/notification/plugin')
        assert 200 == resp.status
        result = await resp.text()
        json_response = json.loads(result)
        assert rules_and_delivery == json_response

    async def test_get_notification(self, mocker, client):
        notif = {
            "name": notification_config['name']['value'],
            "description": notification_config['description']['value'],
            "rule": notification_config['rule']['value'],
            "ruleConfig": rule_config[notification_config['rule']['value']],
            "channel": notification_config['channel']['value'],
            "deliveryConfig": delivery_config[notification_config['channel']['value']],
            "notificationType": notification_config['notification_type']['value'],
            "enable": notification_config['enable']['value'],
        }

        mocker.patch.object(connect, 'get_storage_async')
        mocker.patch.object(ConfigurationManager, '__init__', return_value=None)
        mocker.patch.object(ConfigurationManager, '_read_category_val', side_effect=[
            mock_read_category_val("Test Notification"),
            mock_read_category_val("ruleTest Notification"),
            mock_read_category_val("deliveryTest Notification")])

        resp = await client.get('/foglamp/notification/Test Notification')
        assert 200 == resp.status
        result = await resp.text()
        json_response = json.loads(result)
        assert notif == json_response["notification"]

    async def test_get_notifications(self, mocker, client):
        notifications = [{
            "name": notification_config['name']['value'],
            "rule": notification_config['rule']['value'],
            "channel": notification_config['channel']['value'],
            "notificationType": notification_config['notification_type']['value'],
            "enable": notification_config['enable']['value'],
        }]

        mocker.patch.object(connect, 'get_storage_async')
        mocker.patch.object(ConfigurationManager, '__init__', return_value=None)
        mocker.patch.object(ConfigurationManager, '_read_all_child_category_names',
                            return_value=mock_read_all_child_category_names())
        mocker.patch.object(ConfigurationManager, '_read_category_val',
                            return_value=mock_read_category_val("Test Notification"))

        resp = await client.get('/foglamp/notification')
        assert 200 == resp.status
        result = await resp.text()
        json_response = json.loads(result)
        assert notifications == json_response["notifications"]

    async def test_post_notification(self, mocker, client):
        mocker.patch.object(ServiceRegistry, 'get', return_value=mock_registry)
        mocker.patch.object(notification, '_hit_get_url', return_value=mock_get_url("/foglamp/notification/plugin"))
        mocker.patch.object(notification, '_hit_post_url',
                            side_effect=[mock_post_url("/foglamp/notification/Test Notification"),
                                         mock_post_url("/foglamp/notification/Test Notification/rule/threshold"),
                                         mock_post_url("/foglamp/notification/Test Notification/delivery/email")])
        mocker.patch.object(connect, 'get_storage_async')
        mocker.patch.object(ConfigurationManager, '__init__', return_value=None)
        create_category = mocker.patch.object(ConfigurationManager, 'create_category',
                                              return_value=mock_create_category())
        create_child_category = mocker.patch.object(ConfigurationManager, 'create_child_category',
                                                    return_value=mock_create_child_category())
        mocker.patch.object(ConfigurationManager, '_read_category_val', return_value=mock_read_category_val())
        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": "threshold", ' \
                       '"channel": "email", "notification_type": "one shot", "enabled": false}'

        resp = await client.post("/foglamp/notification", data=mock_payload)
        assert 200 == resp.status
        result = await resp.json()
        assert result['result'].endswith("Notification {} created successfully".format("Test Notification"))

        create_category_calls = [call(category_description='Test Notification', category_name='Test Notification',
                                      category_value={'rule': {'default': 'threshold', 'type': 'string',
                                                               'description': 'Rule to evaluate'},
                                                      'channel': {'default': 'email', 'type': 'string',
                                                                  'description': 'Channel to send alert on'},
                                                      'enable': {'default': 'false', 'type': 'boolean',
                                                                 'description': 'Enabled'},
                                                      'notification_type': {'default': 'one shot',
                                                                            'options': ['one shot', 'retriggered',
                                                                                        'toggled'],
                                                                            'type': 'enumeration',
                                                                            'description': 'Type of notification'},
                                                      'name': {'default': 'Test Notification', 'type': 'string',
                                                               'description': 'The name of this notification'},
                                                      'description': {'default': 'Test Notification', 'type': 'string',
                                                                      'description': 'Description of this notification'}},
                                      keep_original_items=True),
                                 call('Notifications', {}, 'Notifications', True),
                                 call(category_description='The accepted tolerance',
                                      category_name='ruleTest Notification', category_value={
                                         'tolerance': {'default': '4', 'type': 'integer', 'value': '4',
                                                       'description': 'The accepted tolerance'},
                                         'trigger': {'default': '40', 'type': 'integer', 'value': '40',
                                                     'description': 'Temparature threshold value'},
                                         'plugin': {'default': 'threshold', 'type': 'string', 'value': 'threshold',
                                                    'description': 'The accepted tolerance'},
                                         'window': {'default': '60', 'type': 'integer', 'value': '60',
                                                    'description': 'The window to perform rule evaluation over in minutes'},
                                         'asset': {'default': 'temperature', 'type': 'string', 'value': 'temperature',
                                                   'description': 'The asset the notification is defined against'}},
                                      keep_original_items=True),
                                 call(category_description='Email', category_name='deliveryTest Notification',
                                      category_value={'to': {'default': 'test', 'type': 'string', 'value': 'test',
                                                             'description': 'The address to send the notification to'},
                                                      'from': {'default': 'foglamp', 'type': 'string',
                                                               'value': 'foglamp',
                                                               'description': 'The from address to use in the email'},
                                                      'server': {'default': 'smtp', 'type': 'string', 'value': 'smtp',
                                                                 'description': 'The smtp server'},
                                                      'plugin': {'default': 'email', 'type': 'string', 'value': 'email',
                                                                 'description': 'Email'}}, keep_original_items=True)]
        create_category.assert_has_calls(create_category_calls, any_order=True)
        create_child_category_calls = [call('Notifications', ['Test Notification']),
                                       call('Test Notification', ['ruleTest Notification']),
                                       call('Test Notification', ['deliveryTest Notification'])]
        create_child_category.assert_has_calls(create_child_category_calls, any_order=True)

    async def test_post_notification_exception(self, mocker, client):
        mocker.patch.object(ServiceRegistry, 'get', return_value=mock_registry)
        mocker.patch.object(notification, '_hit_get_url', return_value=mock_get_url("/foglamp/notification/plugin"))
        mocker.patch.object(notification, '_hit_post_url',
                            side_effect=[mock_post_url("/foglamp/notification/Test Notification"),
                                         mock_post_url("/foglamp/notification/Test Notification/rule/threshold"),
                                         mock_post_url("/foglamp/notification/Test Notification/delivery/email")])
        mocker.patch.object(connect, 'get_storage_async')
        mocker.patch.object(ConfigurationManager, '__init__', return_value=None)
        create_category = mocker.patch.object(ConfigurationManager, 'create_category',
                                              return_value=mock_create_category())
        create_child_category = mocker.patch.object(ConfigurationManager, 'create_child_category',
                                                    return_value=mock_create_child_category())
        mocker.patch.object(ConfigurationManager, '_read_category_val', return_value=mock_read_category_val())

        mock_payload = '{"description":"Test Notification", "rule": "threshold", "channel": "email", ' \
                       '"notification_type": "one shot", "enabled": false}'
        resp = await client.post("/foglamp/notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Missing name property in payload.')

        mock_payload = '{"name": "", "description":"Test Notification", "rule": "threshold", "channel": "email", ' \
                       '"notification_type": "one shot", "enabled": false}'
        resp = await client.post("/foglamp/notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Missing name property in payload.')

        mock_payload = '{"name": "Test Notification", "rule": "threshold", "channel": "email", ' \
                       '"notification_type": "one shot", "enabled": false}'
        resp = await client.post("/foglamp/notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Missing description property in payload.')

        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "channel": "email", ' \
                       '"notification_type": "one shot", "enabled": false}'
        resp = await client.post("/foglamp/notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Missing rule property in payload.')

        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": "threshold", ' \
                       '"notification_type": "one shot", "enabled": false}'
        resp = await client.post("/foglamp/notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Missing channel property in payload.')

        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": "threshold", ' \
                       '"channel": "email", "enabled": false}'
        resp = await client.post("/foglamp/notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Missing notification_type property in payload.')

        mock_payload = '{"name": ";", "description":"Test Notification", "rule": "threshold", "channel": "email", ' \
                       '"notification_type": "one shot", "enabled": false}'
        resp = await client.post("/foglamp/notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Invalid name property in payload.')

        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": ";", ' \
                       '"channel": "email", "notification_type": "one shot", "enabled": false}'
        resp = await client.post("/foglamp/notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Invalid rule property in payload.')

        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": "threshold", ' \
                       '"channel": ";", "notification_type": "one shot", "enabled": false}'
        resp = await client.post("/foglamp/notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Invalid channel property in payload.')

        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": "threshold", ' \
                       '"channel": "email", "notification_type": ";", "enabled": false}'
        resp = await client.post("/foglamp/notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Invalid notification_type property in payload.')


        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": "threshold", ' \
                       '"channel": "email", "notification_type": "one shot", "enabled": fals}'
        resp = await client.post("/foglamp/notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Expecting value: line 1 column 151 (char 150)')

        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": "threshol", ' \
                       '"channel": "emai", "notification_type": "one shot", "enabled": false}'
        resp = await client.post("/foglamp/notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith(
            "Invalid rule plugin:[{}] and/or delivery plugin:[{}] supplied.".format("threshol", "emai"))

    async def test_put_notification(self, mocker, client):
        mocker.patch.object(ServiceRegistry, 'get', return_value=mock_registry)
        mocker.patch.object(notification, '_hit_get_url', return_value=mock_get_url("/foglamp/notification/plugin"))
        mocker.patch.object(connect, 'get_storage_async')
        mocker.patch.object(ConfigurationManager, '__init__', return_value=None)
        create_category = mocker.patch.object(ConfigurationManager, 'create_category',
                                              return_value=mock_create_category())
        update_category = mocker.patch.object(ConfigurationManager, '_update_category',
                                              return_value=mock_update_category())
        mocker.patch.object(ConfigurationManager, '_read_category_val',
                            return_value=mock_read_category_val("Test Notification"))
        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": "threshold", ' \
                       '"channel": "sms", "notification_type": "one shot", "enabled": false, ' \
                       '"rule_config": {"plugin": {"value": "threshold", "default": "threshold", ' \
                       '"description": "Updated description", "type": "string"}, "asset": {"value": "temperature", ' \
                       '"default": "temperature", "description": "The asset the notification is defined against", ' \
                       '"type": "string"}, "trigger": {"value": "70", "default": "70", ' \
                       '"description": "Temparature threshold value", "type": "integer"}, ' \
                       '"window": {"value": "60", "default": "60", ' \
                       '"description": "The window to perform rule evaluation over in minutes", "type": "integer"}, ' \
                       '"tolerance": {"value": "4", "default": "4", "description": "The accepted tolerance", ' \
                       '"type": "integer"}}, ' \
                       '"delivery_config": {"plugin": {"value": "sms", "default": "sms", "description": "SMS", ' \
                       '"type": "string"}, "number": {"value": "07812 343830", "default": "07812 343830", ' \
                       '"description": "The phone number to call", "type": "string"}} }'

        resp = await client.put("/foglamp/notification/Test Notification", data=mock_payload)
        assert 200 == resp.status
        result = await resp.json()
        assert result['result'].endswith("Notification {} updated successfully".format("Test Notification"))

        create_category_calls = [call(category_description='Test Notification', category_name='Test Notification',
                                      category_value={'description': {'description': 'Description of this notification',
                                                                      'type': 'string', 'default': 'Test Notification'},
                                                      'channel': {'description': 'Channel to send alert on',
                                                                  'type': 'string', 'default': 'sms'},
                                                      'rule': {'description': 'Rule to evaluate', 'type': 'string',
                                                               'default': 'threshold'},
                                                      'enable': {'description': 'Enabled', 'type': 'boolean',
                                                                 'default': 'false'}, 'notification_type': {
                                              'options': ['one shot', 'retriggered', 'toggled'],
                                              'description': 'Type of notification', 'type': 'enumeration',
                                              'default': 'one shot'},
                                                      'name': {'description': 'The name of this notification',
                                                               'type': 'string', 'default': 'Test Notification'}},
                                      keep_original_items=True)]
        create_category.assert_has_calls(create_category_calls, any_order=True)
        update_category_calls = [call(category_description='Updated description', category_name='ruleTest Notification',
                                      category_val={'asset': {'type': 'string',
                                                              'description': 'The asset the notification is defined against',
                                                              'default': 'temperature', 'value': 'temperature'},
                                                    'plugin': {'type': 'string', 'description': 'Updated description',
                                                               'default': 'threshold', 'value': 'threshold'},
                                                    'trigger': {'type': 'integer',
                                                                'description': 'Temparature threshold value',
                                                                'default': '70', 'value': '70'},
                                                    'window': {'type': 'integer',
                                                               'description': 'The window to perform rule evaluation over in minutes',
                                                               'default': '60', 'value': '60'},
                                                    'tolerance': {'type': 'integer',
                                                                  'description': 'The accepted tolerance',
                                                                  'default': '4', 'value': '4'}}),
                                 call(category_description='SMS', category_name='deliveryTest Notification',
                                      category_val={'plugin': {'type': 'string', 'description': 'SMS', 'default': 'sms',
                                                               'value': 'sms'}, 'number': {'type': 'string',
                                                                                           'description': 'The phone number to call',
                                                                                           'default': '07812 343830',
                                                                                           'value': '07812 343830'}})]
        update_category.assert_has_calls(update_category_calls, any_order=True)

    async def test_put_notification_exception(self, mocker, client):
        mocker.patch.object(ServiceRegistry, 'get', return_value=mock_registry)
        mocker.patch.object(notification, '_hit_get_url', return_value=mock_get_url("/foglamp/notification/plugin"))
        mocker.patch.object(connect, 'get_storage_async')
        mocker.patch.object(ConfigurationManager, '__init__', return_value=None)
        create_category = mocker.patch.object(ConfigurationManager, 'create_category',
                                              return_value=mock_create_category())
        update_category = mocker.patch.object(ConfigurationManager, '_update_category',
                                              return_value=mock_update_category())
        mocker.patch.object(ConfigurationManager, '_read_category_val',
                            return_value=mock_read_category_val("Test Notification"))

        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": "threshold", ' \
                       '"channel": "email", "notification_type": "one shot", "enabled": false, ' \
                       '"rule_config": {"plugin": {"value": "threshold", "default": "threshold", ' \
                       '"description": "Updated description", "type": "string"}, "asset": {"value": "temperature", ' \
                       '"default": "temperature", "description": "The asset the notification is defined against", ' \
                       '"type": "string"}, "trigger": {"value": "70", "default": "70", ' \
                       '"description": "Temparature threshold value", "type": "integer"}, ' \
                       '"window": {"value": "60", "default": "60", ' \
                       '"description": "The window to perform rule evaluation over in minutes", "type": "integer"}, ' \
                       '"tolerance": {"value": "4", "default": "4", "description": "The accepted tolerance", ' \
                       '"type": "integer"}}, ' \
                       '"delivery_config": {"plugin": {"value": "sms", "default": "sms", "description": "SMS", ' \
                       '"type": "string"}, "number": {"value": "07812 343830", "default": "07812 343830", ' \
                       '"description": "The phone number to call", "type": "string"}} }'
        resp = await client.put("/foglamp/notification", data=mock_payload)
        assert 405 == resp.status
        result = await resp.text()
        assert result.endswith(" Method Not Allowed")

        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": ";", ' \
                       '"channel": "email", "notification_type": "one shot", "enabled": false, ' \
                       '"rule_config": {"plugin": {"value": "threshold", "default": "threshold", ' \
                       '"description": "Updated description", "type": "string"}, "asset": {"value": "temperature", ' \
                       '"default": "temperature", "description": "The asset the notification is defined against", ' \
                       '"type": "string"}, "trigger": {"value": "70", "default": "70", ' \
                       '"description": "Temparature threshold value", "type": "integer"}, ' \
                       '"window": {"value": "60", "default": "60", ' \
                       '"description": "The window to perform rule evaluation over in minutes", "type": "integer"}, ' \
                       '"tolerance": {"value": "4", "default": "4", "description": "The accepted tolerance", ' \
                       '"type": "integer"}}, ' \
                       '"delivery_config": {"plugin": {"value": "sms", "default": "sms", "description": "SMS", ' \
                       '"type": "string"}, "number": {"value": "07812 343830", "default": "07812 343830", ' \
                       '"description": "The phone number to call", "type": "string"}} }'
        resp = await client.put("/foglamp/notification/Test Notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Invalid rule property in payload.')

        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": "threshold", ' \
                       '"channel": ";", "notification_type": "one shot", "enabled": false, ' \
                       '"rule_config": {"plugin": {"value": "threshold", "default": "threshold", ' \
                       '"description": "Updated description", "type": "string"}, ' \
                       '"asset": {"value": "temperature", "default": "temperature", ' \
                       '"description": "The asset the notification is defined against", "type": "string"}, ' \
                       '"trigger": {"value": "70", "default": "70", ' \
                       '"description": "Temparature threshold value", "type": "integer"}, ' \
                       '"window": {"value": "60", "default": "60", ' \
                       '"description": "The window to perform rule evaluation over in minutes", "type": "integer"}, ' \
                       '"tolerance": {"value": "4", "default": "4", "description": "The accepted tolerance", ' \
                       '"type": "integer"}}, ' \
                       '"delivery_config": {"plugin": {"value": "sms", "default": "sms", "description": "SMS", ' \
                       '"type": "string"}, "number": {"value": "07812 343830", "default": "07812 343830", ' \
                       '"description": "The phone number to call", "type": "string"}} }'
        resp = await client.put("/foglamp/notification/Test Notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Invalid channel property in payload.')

        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": "threshold", ' \
                       '"channel": "sms", "notification_type": ";", "enabled": false, ' \
                       '"rule_config": {"plugin": {"value": "threshold", "default": "threshold", ' \
                       '"description": "Updated description", "type": "string"}, "asset": {"value": "temperature", ' \
                       '"default": "temperature", "description": "The asset the notification is defined against", ' \
                       '"type": "string"}, "trigger": {"value": "70", "default": "70", "description": ' \
                       '"Temparature threshold value", "type": "integer"}, "window": {"value": "60", "default": "60", ' \
                       '"description": "The window to perform rule evaluation over in minutes", "type": "integer"}, ' \
                       '"tolerance": {"value": "4", "default": "4", "description": "The accepted tolerance", ' \
                       '"type": "integer"}}, ' \
                       '"delivery_config": {"plugin": {"value": "sms", "default": "sms", "description": "SMS", ' \
                       '"type": "string"}, "number": {"value": "07812 343830", "default": "07812 343830", ' \
                       '"description": "The phone number to call", "type": "string"}} }'
        resp = await client.put("/foglamp/notification/Test Notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Invalid notification_type property in payload.')

        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": "threshold", ' \
                       '"channel": "sms", "notification_type": "one shot", "enabled": fals, ' \
                       '"rule_config": {"plugin": {"value": "threshold", "default": "threshold", ' \
                       '"description": "Updated description", "type": "string"}, "asset": {"value": "temperature", ' \
                       '"default": "temperature", "description": "The asset the notification is defined against", ' \
                       '"type": "string"}, "trigger": {"value": "70", "default": "70", ' \
                       '"description": "Temparature threshold value", "type": "integer"}, ' \
                       '"window": {"value": "60", "default": "60", ' \
                       '"description": "The window to perform rule evaluation over in minutes", ' \
                       '"type": "integer"}, "tolerance": {"value": "4", "default": "4", ' \
                       '"description": "The accepted tolerance", "type": "integer"}}, ' \
                       '"delivery_config": {"plugin": {"value": "sms", "default": "sms", "description": "SMS", ' \
                       '"type": "string"}, "number": {"value": "07812 343830", "default": "07812 343830", ' \
                       '"description": "The phone number to call", "type": "string"}} }'
        resp = await client.put("/foglamp/notification/Test Notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith('Expecting value: line 1 column 149 (char 148)')

        mock_payload = '{"name": "Test Notification", "description":"Test Notification", "rule": "threshol", ' \
                       '"channel": "sm", "notification_type": "one shot", "enabled": false, ' \
                       '"rule_config": {"plugin": {"value": "threshold", "default": "threshold", ' \
                       '"description": "Updated description", "type": "string"}, "asset": {"value": "temperature", ' \
                       '"default": "temperature", "description": "The asset the notification is defined against", ' \
                       '"type": "string"}, "trigger": {"value": "70", "default": "70", ' \
                       '"description": "Temparature threshold value", "type": "integer"}, ' \
                       '"window": {"value": "60", "default": "60", ' \
                       '"description": "The window to perform rule evaluation over in minutes", ' \
                       '"type": "integer"}, "tolerance": {"value": "4", "default": "4", ' \
                       '"description": "The accepted tolerance", "type": "integer"}}, ' \
                       '"delivery_config": {"plugin": {"value": "sms", "default": "sms", ' \
                       '"description": "SMS", "type": "string"}, "number": {"value": "07812 343830", ' \
                       '"default": "07812 343830", "description": "The phone number to call", "type": "string"}} }'
        resp = await client.put("/foglamp/notification/Test Notification", data=mock_payload)
        assert 400 == resp.status
        result = await resp.text()
        assert result.endswith(
            "Invalid rule plugin:[{}] and/or delivery plugin:[{}] supplied.".format("threshol", "sm"))

    async def test_delete_notification(self, mocker, client):
        mocker.patch.object(ServiceRegistry, 'get', return_value=mock_registry)
        mocker.patch.object(notification, '_hit_get_url', return_value=mock_get_url("/foglamp/notification/plugin"))
        mocker.patch.object(connect, 'get_storage_async')
        mocker.patch.object(ConfigurationManager, '__init__', return_value=None)
        mocker.patch.object(ConfigurationManager, '_read_category_val',
                            return_value=mock_read_category_val("Test Notification"))
        delete_configuration = mocker.patch.object(notification, "_delete_configuration",
                                                   return_value=asyncio.sleep(.1))
        mocker.patch.object(AuditLogger, "__init__", return_value=None)
        audit_logger = mocker.patch.object(AuditLogger, "information", return_value=asyncio.sleep(.1))

        resp = await client.delete("/foglamp/notification/Test Notification")
        assert 200 == resp.status
        result = await resp.json()
        assert result['result'].endswith("Notification {} deleted successfully.".format("Test Notification"))
        args, kwargs = delete_configuration.call_args_list[0]
        assert "Test Notification" in args

        assert 1 == audit_logger.call_count
        audit_logger_calls = [call('NTFDL', {'delivery': {
            'sms': {'plugin': {'default': 'sms', 'type': 'string', 'description': 'SMS', 'value': 'sms'},
                    'number': {'default': '07812 343830', 'type': 'string', 'description': 'The phone number to call',
                               'value': '07812 343830'}}, 'email': {
                'to': {'default': 'test', 'type': 'string', 'description': 'The address to send the notification to',
                       'value': 'test'},
                'plugin': {'default': 'email', 'type': 'string', 'description': 'Email', 'value': 'email'},
                'server': {'default': 'smtp', 'type': 'string', 'description': 'The smtp server', 'value': 'smtp'},
                'from': {'default': 'foglamp', 'type': 'string', 'description': 'The from address to use in the email',
                         'value': 'foglamp'}}}, 'rules': {'threshold': {
            'trigger': {'default': '40', 'type': 'integer', 'description': 'Temparature threshold value',
                        'value': '40'}, 'window': {'default': '60', 'type': 'integer',
                                                   'description': 'The window to perform rule evaluation over in minutes',
                                                   'value': '60'}, 'asset': {'default': 'temperature', 'type': 'string',
                                                                             'description': 'The asset the notification is defined against',
                                                                             'value': 'temperature'},
            'tolerance': {'default': '4', 'type': 'integer', 'description': 'The accepted tolerance', 'value': '4'},
            'plugin': {'default': 'threshold', 'type': 'string', 'description': 'The accepted tolerance',
                       'value': 'threshold'}}}})]
        audit_logger.assert_has_calls(audit_logger_calls, any_order=True)

    async def test_delete_notification_exception(self, mocker, client):
        mocker.patch.object(ServiceRegistry, 'get', return_value=mock_registry)
        mocker.patch.object(notification, '_hit_get_url', return_value=mock_get_url("/foglamp/notification/plugin"))
        mocker.patch.object(connect, 'get_storage_async')
        mocker.patch.object(ConfigurationManager, '__init__', return_value=None)
        mocker.patch.object(ConfigurationManager, '_read_category_val',
                            return_value=mock_read_category_val("Test Notification"))
        delete_configuration = mocker.patch.object(notification, "_delete_configuration",
                                                   return_value=asyncio.sleep(.1))
        mocker.patch.object(AuditLogger, "__init__", return_value=None)
        audit_logger = mocker.patch.object(AuditLogger, "information", return_value=asyncio.sleep(.1))

        resp = await client.delete("/foglamp/notification")
        assert 405 == resp.status
        result = await resp.text()
        assert result.endswith(" Method Not Allowed")

    async def test_registry_exception(self, mocker, client):
        mocker.patch.object(ServiceRegistry, 'get', side_effect=service_registry_exceptions.DoesNotExist)
        resp = await client.delete("/foglamp/notification/Test Notification")
        assert 404 == resp.status
        result = await resp.text()
        assert result.endswith("No Notification service available.")
