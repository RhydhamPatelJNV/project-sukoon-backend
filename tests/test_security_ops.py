import os
import sys
import unittest

backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from sukoon.security.vault import SecurityVault, SecretRedactor
from sukoon.ops.telegram import TelegramAlertDispatcher
from sukoon.ops.safe_mode import SafeModeManager, IncidentClass
from sukoon.guardian.kill_switch import KillSwitchController
from sukoon.guardian.live_activation import LiveActivationProtocol

class TestSecurityAndOperations(unittest.TestCase):
    def test_aes_gcm_vault_encryption_roundtrip(self):
        vault = SecurityVault()
        raw_secret = "PK_ALPACA_LIVE_SECRET_KEY_1234567890"

        encrypted = vault.encrypt(raw_secret)
        self.assertNotEqual(encrypted, raw_secret)

        decrypted = vault.decrypt(encrypted)
        self.assertEqual(decrypted, raw_secret)

    def test_secret_redactor_masks_credentials(self):
        log_line = "Failed to authenticate with key PK123456789012345678 and secret sk-abcdef123456789012345678."
        redacted = SecretRedactor.redact(log_line)
        self.assertNotIn("PK123456789012345678", redacted)
        self.assertNotIn("sk-abcdef123456789012345678", redacted)
        self.assertIn("[REDACTED_SECRET]", redacted)

    def test_safe_mode_p0_incident_escalation(self):
        ks = KillSwitchController()
        alerts = TelegramAlertDispatcher(mock_mode=True)
        sm = SafeModeManager(kill_switch=ks, alert_dispatcher=alerts)

        # Trigger P0 incident
        sm.handle_incident(
            incident_class=IncidentClass.P0,
            title="Unauthorized Execution Attempt",
            details="Rogue order bypassed validation gate"
        )
        self.assertTrue(ks.is_active)
        dispatched = alerts.get_dispatched_alerts()
        self.assertEqual(len(dispatched), 1)
        self.assertEqual(dispatched[0].severity, "P0_CRITICAL")
        self.assertIn("EMERGENCY", dispatched[0].title)

    def test_live_activation_requires_lrs_acknowledgement(self):
        # Activation without LRS acknowledgement must fail
        with self.assertRaises(ValueError):
            LiveActivationProtocol.issue_activation_certificate(
                account_alias="alpaca-live-main",
                authorized_strategies=["strat_spy_trend"],
                max_capital_usd=10000.0,
                lrs_confirmed=False, # BLOCKED
                user_identity="AuthorizedUser",
                secret_key="SUPER_SECRET_SIGNING_KEY"
            )

        # Valid activation with LRS acknowledgement
        cert = LiveActivationProtocol.issue_activation_certificate(
            account_alias="alpaca-live-main",
            authorized_strategies=["strat_spy_trend"],
            max_capital_usd=10000.0,
            lrs_confirmed=True,
            user_identity="AuthorizedUser",
            secret_key="SUPER_SECRET_SIGNING_KEY"
        )
        self.assertTrue(cert.signature)
        self.assertEqual(cert.max_capital_allocation_usd, 10000.0)

if __name__ == "__main__":
    unittest.main()
