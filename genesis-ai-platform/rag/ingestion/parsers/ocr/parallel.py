"""
OCR 并行处理模块

特性：
1. 线程池并行执行多变体/多 PSM 识别
2. 自动错误处理和降级
3. 超时保护
4. 结果合并
"""

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ParallelOCRExecutor:
    """
    并行 OCR 执行器
    
    使用线程池并行执行多个 OCR 任务，提升多变体/多 PSM 场景的性能
    """
    
    def __init__(self, max_workers: int = 4, timeout_seconds: int = 30):
        """
        初始化并行执行器
        
        Args:
            max_workers: 最大工作线程数（默认 4）
            timeout_seconds: 单个任务超时时间（秒，默认 30）
        """
        self.max_workers = max_workers
        self.timeout_seconds = timeout_seconds
    
    def execute_parallel(
        self,
        tasks: List[Tuple[str, Callable, Tuple, Dict]],
    ) -> List[Tuple[str, Optional[Any], Optional[Exception]]]:
        """
        并行执行多个 OCR 任务
        
        Args:
            tasks: 任务列表，每个任务为 (task_id, func, args, kwargs)
        
        Returns:
            结果列表，每个结果为 (task_id, result, error)
        """
        if not tasks:
            return []
        
        # 如果只有一个任务，直接执行（避免线程池开销）
        if len(tasks) == 1:
            task_id, func, args, kwargs = tasks[0]
            try:
                result = func(*args, **kwargs)
                return [(task_id, result, None)]
            except Exception as e:
                logger.error(f"[ParallelOCR] 任务 {task_id} 执行失败: {e}")
                return [(task_id, None, e)]
        
        # 多任务并行执行
        results: List[Tuple[str, Optional[Any], Optional[Exception]]] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_task = {}
            for task_id, func, args, kwargs in tasks:
                future = executor.submit(func, *args, **kwargs)
                future_to_task[future] = task_id
            
            # 收集结果
            for future in as_completed(future_to_task, timeout=self.timeout_seconds * len(tasks)):
                task_id = future_to_task[future]
                try:
                    result = future.result(timeout=self.timeout_seconds)
                    results.append((task_id, result, None))
                    logger.debug(f"[ParallelOCR] 任务 {task_id} 完成")
                except TimeoutError:
                    error = TimeoutError(f"任务 {task_id} 超时")
                    results.append((task_id, None, error))
                    logger.error(f"[ParallelOCR] 任务 {task_id} 超时")
                except Exception as e:
                    results.append((task_id, None, e))
                    logger.error(f"[ParallelOCR] 任务 {task_id} 失败: {e}")
        
        return results
    
    def recognize_variants_parallel(
        self,
        variants: List[Tuple[str, Any]],
        recognize_func: Callable,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        并行识别多个图像变体
        
        Args:
            variants: 变体列表 [(variant_name, variant_image), ...]
            recognize_func: 识别函数
            **kwargs: 传递给识别函数的额外参数
        
        Returns:
            合并后的识别结果列表
        """
        if not variants:
            return []
        
        # 构建任务列表
        tasks: List[Tuple[str, Callable, Tuple, Dict[str, Any]]] = []
        for variant_name, variant_image in variants:
            task_id = f"variant_{variant_name}"
            tasks.append((
                task_id,
                recognize_func,
                (variant_image,),
                {**kwargs, "variant_name": variant_name}
            ))
        
        # 并行执行
        results = self.execute_parallel(tasks)
        
        # 合并结果
        all_lines: List[Dict[str, Any]] = []
        for task_id, result, error in results:
            if error is None and result:
                all_lines.extend(result)
            elif error:
                logger.warning(f"[ParallelOCR] 变体识别失败: {task_id}, error={error}")
        
        return all_lines
    
    def recognize_psm_parallel(
        self,
        image: Any,
        psm_list: List[int],
        recognize_func: Callable,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        并行识别多个 PSM 模式
        
        Args:
            image: 图像对象
            psm_list: PSM 模式列表
            recognize_func: 识别函数
            **kwargs: 传递给识别函数的额外参数
        
        Returns:
            合并后的识别结果列表
        """
        if not psm_list:
            return []
        
        # 构建任务列表
        tasks: List[Tuple[str, Callable, Tuple, Dict[str, Any]]] = []
        for psm in psm_list:
            task_id = f"psm_{psm}"
            tasks.append((
                task_id,
                recognize_func,
                (image,),
                {**kwargs, "psm": psm}
            ))
        
        # 并行执行
        results = self.execute_parallel(tasks)
        
        # 合并结果
        all_lines: List[Dict[str, Any]] = []
        for task_id, result, error in results:
            if error is None and result:
                all_lines.extend(result)
            elif error:
                logger.warning(f"[ParallelOCR] PSM 识别失败: {task_id}, error={error}")
        
        return all_lines
    
    def recognize_variants_and_psm_parallel(
        self,
        variants: List[Tuple[str, Any]],
        psm_list: List[int],
        recognize_func: Callable,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        并行识别多个变体和多个 PSM 模式（笛卡尔积）
        
        Args:
            variants: 变体列表 [(variant_name, variant_image), ...]
            psm_list: PSM 模式列表
            recognize_func: 识别函数
            **kwargs: 传递给识别函数的额外参数
        
        Returns:
            合并后的识别结果列表
        """
        if not variants or not psm_list:
            return []
        
        # 构建任务列表（变体 × PSM）
        tasks: List[Tuple[str, Callable, Tuple, Dict[str, Any]]] = []
        for variant_name, variant_image in variants:
            for psm in psm_list:
                task_id = f"variant_{variant_name}_psm_{psm}"
                tasks.append((
                    task_id,
                    recognize_func,
                    (variant_image,),
                    {**kwargs, "variant_name": variant_name, "psm": psm}
                ))
        
        # 并行执行
        logger.info(f"[ParallelOCR] 开始并行识别: {len(variants)} 变体 × {len(psm_list)} PSM = {len(tasks)} 任务")
        results = self.execute_parallel(tasks)
        
        # 合并结果
        all_lines: List[Dict[str, Any]] = []
        success_count = 0
        for task_id, result, error in results:
            if error is None and result:
                all_lines.extend(result)
                success_count += 1
            elif error:
                logger.warning(f"[ParallelOCR] 任务失败: {task_id}, error={error}")
        
        logger.info(f"[ParallelOCR] 并行识别完成: {success_count}/{len(tasks)} 成功, 识别行数={len(all_lines)}")
        return all_lines


# 全局并行执行器实例（单例模式）
_global_executor: Optional[ParallelOCRExecutor] = None


def get_global_executor(max_workers: int = 4, timeout_seconds: int = 30) -> ParallelOCRExecutor:
    """
    获取全局并行执行器实例（单例模式）
    
    Args:
        max_workers: 最大工作线程数
        timeout_seconds: 单个任务超时时间（秒）
    
    Returns:
        全局 ParallelOCRExecutor 实例
    """
    global _global_executor
    
    if _global_executor is None:
        _global_executor = ParallelOCRExecutor(
            max_workers=max_workers,
            timeout_seconds=timeout_seconds
        )
        logger.info(f"[ParallelOCR] 初始化全局执行器: max_workers={max_workers}, timeout={timeout_seconds}s")
    
    return _global_executor
