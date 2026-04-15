"""
节点转换器 - 将 LlamaIndex 节点转换为内部统一格式
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class NodeConverter:
    """LlamaIndex 节点转换器"""

    @staticmethod
    def _build_content_blocks(content: str, chunk_type: str) -> List[Dict[str, Any]]:
        """统一构造结构化内容块。"""
        return [
            {
                "block_id": "b1",
                "type": str(chunk_type or "text").lower(),
                "text": content,
                "source_refs": [],
            }
        ]

    @staticmethod
    def convert_nodes_to_chunks(nodes: List[Any], is_hierarchical: bool = False) -> List[Dict[str, Any]]:
        """
        将 LlamaIndex 节点转换为内部格式，并进行层级裁剪去重。
        """
        node_map = {node.node_id: node for node in nodes}

        redundant_ids = set()
        for node in nodes:
            content = node.get_content().strip()
            parent_node = node.parent_node
            if parent_node:
                parent_real_node = node_map.get(parent_node.node_id)
                if parent_real_node and parent_real_node.get_content().strip() == content:
                    redundant_ids.add(node.node_id)

        final_chunks = []
        for node in nodes:
            if node.node_id in redundant_ids:
                continue

            content = node.get_content().strip()
            chunk_meta = node.metadata.copy()

            effective_parent_id = NodeConverter._find_effective_parent(node, node_map, redundant_ids)
            effective_child_ids = NodeConverter._find_effective_children(node, node_map, redundant_ids)
            is_root, is_leaf, depth = NodeConverter._determine_topology(
                effective_parent_id,
                effective_child_ids,
            )

            chunk_meta.update(
                {
                    "node_id": node.node_id,
                    "parent_id": effective_parent_id,
                    "child_ids": effective_child_ids,
                    "is_root": is_root,
                    "is_leaf": is_leaf,
                    "depth": depth,
                    "is_smart": True,
                    "is_hierarchical": is_hierarchical,
                    "is_pruned": True,
                    "should_vectorize": is_leaf,
                    "source_anchors": [],
                    "source_element_indices": [],
                    "page_numbers": [],
                }
            )

            final_chunks.append(
                {
                    "text": content,
                    "metadata": chunk_meta,
                    "type": "text",
                    "content_blocks": NodeConverter._build_content_blocks(content, "text"),
                }
            )

        return final_chunks

    @staticmethod
    def _find_effective_parent(node, node_map: Dict[str, Any], redundant_ids: set) -> str | None:
        """向上跳过冗余节点，找到有效父节点。"""
        effective_parent_id = None
        curr_p = node.parent_node

        while curr_p:
            p_id = curr_p.node_id
            if p_id in redundant_ids:
                p_node = node_map.get(p_id)
                curr_p = p_node.parent_node if p_node else None
                continue

            p_node = node_map.get(p_id)
            if not p_node:
                break

            effective_parent_id = p_id
            break

        return effective_parent_id

    @staticmethod
    def _find_effective_children(node, node_map: Dict[str, Any], redundant_ids: set) -> List[str]:
        """向下跳过冗余节点，找到有效子节点。"""
        effective_child_ids = []
        raw_children = getattr(node, "child_nodes", []) or []
        queue = [child.node_id for child in raw_children]

        while queue:
            c_id = queue.pop(0)
            if c_id in redundant_ids:
                c_node = node_map.get(c_id)
                if c_node:
                    c_children = getattr(c_node, "child_nodes", []) or []
                    queue.extend([gc.node_id for gc in c_children])
            else:
                if c_id in node_map:
                    effective_child_ids.append(c_id)

        return effective_child_ids

    @staticmethod
    def _determine_topology(parent_id: str | None, child_ids: List[str]) -> tuple[bool, bool, int]:
        """根据父子关系推导拓扑角色和深度。"""
        has_p = parent_id is not None
        has_c = len(child_ids) > 0

        if not has_p and has_c:
            return True, False, 0
        if not has_p and not has_c:
            return True, True, 0
        if has_p and has_c:
            return False, False, 1
        return False, True, 2
