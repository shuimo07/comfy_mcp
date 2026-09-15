"""
ComfyUI-MiniMax-H3-API
======================
MiniMax H3 视频生成节点（直连 MiniMax 开放平台官方 API，本地不跑模型、不占显存）。

装好这个包之后 ComfyUI 里会多出两个节点，分类在 “MiniMax H3 / API”：
  - MiniMax H3 视频生成 (API)      : 文生视频 / 首帧图生视频 / 首尾帧生视频
  - MiniMax H3 参考生视频 (API)     : 参考图 + 参考视频 + 参考音频 -> 角色/动作/音色一致

API Key 读取顺序：
  1) 节点上的 api_key 输入框（临时）
  2) 环境变量 MINIMAX_API_KEY
  3) E:\\Comfy-Desktop\\ComfyUI-Cache\\minimax_key.txt（单行纯文本）
  4) 本插件目录下的 minimax_key.txt
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
