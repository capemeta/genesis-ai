from abc import ABC, abstractmethod
from typing import Any, Dict, List


class OCREngine(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def recognize(
        self,
        image: Any,
        languages: List[str],
        legacy_mode: bool,
        enhancer: Any,
        psm_list: List[int],
        min_confidence: float,
        enable_parallel: bool = False,
        parallel_executor: Any = None,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError
