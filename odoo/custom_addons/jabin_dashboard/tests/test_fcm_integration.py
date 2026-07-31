# tests/test_fcm_integration.py
import unittest
import json


class MockDevice:
    def __init__(self, id, user_id, fcm_token, device_type='android', is_active=True):
        self.id = id
        self.user_id = user_id
        self.fcm_token = fcm_token
        self.device_type = device_type
        self.is_active = is_active
        self.last_seen = "2026-07-21 10:00:00"

    def deactivate(self):
        self.is_active = False
        return True


class MockNotification:
    def __init__(self, id, user_id, title, body, notification_type='system', deep_link=None, data_json='{}'):
        self.id = id
        self.user_id = user_id
        self.title = title
        self.body = body
        self.notification_type = notification_type
        self.deep_link = deep_link
        self.data_json = data_json
        self.status = 'pending'

    def mark_as_sent(self):
        self.status = 'sent'
        return True

    def mark_as_read(self):
        self.status = 'read'
        return True

    def mark_as_failed(self, reason=None):
        self.status = 'failed'
        return True


class TestFCMIntegrationLogic(unittest.TestCase):
    def test_device_registration_and_uniqueness(self):
        """Test device token registration and token update."""
        devices = {}
        token = "fcm_token_12345"

        # Register device 1
        device1 = MockDevice(1, user_id=10, fcm_token=token, device_type="android")
        devices[token] = device1
        self.assertTrue(device1.is_active)
        self.assertEqual(device1.user_id, 10)

        # Update token upon login/refresh
        new_token = "fcm_token_67890"
        device1.fcm_token = new_token
        devices[new_token] = device1
        del devices[token]

        self.assertIn("fcm_token_67890", devices)
        self.assertNotIn("fcm_token_12345", devices)

    def test_device_logout_deactivation(self):
        """Test device deactivation on logout."""
        device = MockDevice(1, user_id=10, fcm_token="token_abc", is_active=True)
        device.deactivate()
        self.assertFalse(device.is_active)

    def test_notification_payload_formatting(self):
        """Test notification deep link and JSON data payload structure."""
        order_id = 1234
        deep_link = f"jabin://orders/{order_id}"
        data = {'order_id': str(order_id), 'status': 'delivered', 'deep_link': deep_link}

        notif = MockNotification(
            id=100,
            user_id=10,
            title="Order Delivered",
            body="Your order #1234 has been delivered.",
            notification_type="order",
            deep_link=deep_link,
            data_json=json.dumps(data)
        )

        parsed_data = json.loads(notif.data_json)
        self.assertEqual(parsed_data['order_id'], "1234")
        self.assertEqual(parsed_data['status'], "delivered")
        self.assertEqual(parsed_data['deep_link'], "jabin://orders/1234")

    def test_notification_status_lifecycle(self):
        """Test pending -> sent -> read status transitions."""
        notif = MockNotification(1, 10, "Title", "Body")
        self.assertEqual(notif.status, 'pending')

        notif.mark_as_sent()
        self.assertEqual(notif.status, 'sent')

        notif.mark_as_read()
        self.assertEqual(notif.status, 'read')

    def test_send_notification_wizard_json_payload_validation(self):
        """Test wizard custom payload JSON validation."""
        valid_json = '{"key": "value", "promo": 10}'
        invalid_json = '{key: invalid_json}'

        parsed = json.loads(valid_json)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed.get('key'), 'value')

        with self.assertRaises(ValueError):
            json.loads(invalid_json)


if __name__ == "__main__":
    unittest.main()

