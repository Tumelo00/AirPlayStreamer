"""Regression tests for network interface selection and resampler fallback.

Run: python -m unittest tests.test_core
No live VPN or AirPlay device required.
"""

import os
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.network import find_lan_route, patch_pyatv_connection
from core.resampler import Resampler, resampler_backend


class FakeIP:
    def __init__(self, ip, prefix):
        self.ip = ip
        self.network_prefix = prefix


class FakeAdapter:
    def __init__(self, name, ips):
        self.nice_name = name
        self.name = name
        self.ips = ips


class TestNetworkRoute(unittest.TestCase):
    """find_lan_route() interface selection."""

    @patch("ifaddr.get_adapters")
    def test_lan_interface_selected(self, mock_adapters):
        # HomePod on 192.168.31.x -> physical LAN interface chosen
        mock_adapters.return_value = [
            FakeAdapter("Realtek Gaming 2.5GbE",
                        [FakeIP("192.168.31.73", 24)]),
        ]
        ip, name = find_lan_route("192.168.31.30")
        self.assertEqual(ip, "192.168.31.73")
        self.assertIn("Realtek", name)

    @patch("ifaddr.get_adapters")
    def test_vpn_deprioritized(self, mock_adapters):
        # Target sits in both a VPN-named adapter's subnet and a LAN
        # adapter's subnet -> LAN must win.
        mock_adapters.return_value = [
            FakeAdapter("Tailscale", [FakeIP("10.0.0.5", 8)]),     # 10/8
            FakeAdapter("Realtek LAN", [FakeIP("10.1.2.4", 24)]),  # 10.1.2/24
        ]
        ip, name = find_lan_route("10.1.2.3")
        self.assertEqual(ip, "10.1.2.4")
        self.assertIn("Realtek", name)

    @patch("ifaddr.get_adapters")
    def test_no_lan_returns_none(self, mock_adapters):
        # No interface contains the target -> fallback (None, None)
        mock_adapters.return_value = [
            FakeAdapter("Realtek", [FakeIP("192.168.1.5", 24)]),
        ]
        ip, name = find_lan_route("100.88.55.115")
        self.assertIsNone(ip)
        self.assertIsNone(name)

    def test_invalid_target_no_crash(self):
        self.assertEqual(find_lan_route("not-an-ip"), (None, None))

    @patch("ifaddr.get_adapters", side_effect=RuntimeError("boom"))
    def test_ifaddr_failure_no_crash(self, _mock):
        self.assertEqual(find_lan_route("192.168.1.1"), (None, None))

    def test_patch_never_raises(self):
        # patch_pyatv_connection must never raise, even called repeatedly
        patch_pyatv_connection()
        patch_pyatv_connection()


class TestResampler(unittest.TestCase):
    """Resampler with soxr or numpy fallback."""

    def test_backend_is_known(self):
        self.assertIn(resampler_backend(), ("soxr", "numpy-linear"))

    def test_passthrough_same_rate(self):
        r = Resampler(44100, 44100, 2)
        arr = np.zeros((100, 2), dtype=np.int16)
        out = r.process(arr)
        self.assertEqual(out.shape, arr.shape)

    def test_numpy_fallback_resamples(self):
        # Force the numpy path (simulate soxr unavailable)
        r = Resampler(48000, 44100, 2)
        r._soxr_stream = None
        out = r.process(np.zeros((480, 2), dtype=np.int16))
        self.assertGreater(out.shape[0], 0)
        self.assertEqual(out.shape[1], 2)
        self.assertEqual(out.dtype, np.int16)

    def test_empty_input_no_crash(self):
        r = Resampler(48000, 44100, 2)
        r._soxr_stream = None
        out = r.process(np.zeros((0, 2), dtype=np.int16))
        self.assertEqual(out.shape[0], 0)


if __name__ == "__main__":
    unittest.main()
