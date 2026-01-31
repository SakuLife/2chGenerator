"""
VOICEVOX 音声合成スキル
ローカルのVOICEVOX APIを使用して音声を生成
"""

from .client import VoicevoxClient
from .launcher import VoicevoxLauncher

__all__ = ["VoicevoxClient", "VoicevoxLauncher"]
