from __future__ import annotations

import asyncio
import base64
import io
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core import config, default_logger
from app.dtos.vision import VisionCandidate, VisionDetection, VisionIdentifyResponse


class VisionServiceError(Exception):
    def __init__(self, *, error_code: str, message: str, status_code: int) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class VisionImageRequiredError(VisionServiceError):
    def __init__(self) -> None:
        super().__init__(
            error_code="IMAGE_REQUIRED",
            message="업로드 이미지가 필요합니다.",
            status_code=400,
        )


class VisionInvalidImageError(VisionServiceError):
    def __init__(self) -> None:
        super().__init__(
            error_code="INVALID_IMAGE",
            message="이미지 파일을 열 수 없습니다.",
            status_code=400,
        )


class VisionUnsupportedImageError(VisionServiceError):
    def __init__(self) -> None:
        super().__init__(
            error_code="UNSUPPORTED_IMAGE_FORMAT",
            message="지원하지 않는 이미지 형식입니다. (jpg, jpeg, png, webp)",
            status_code=400,
        )


class VisionNoPillDetectedError(VisionServiceError):
    def __init__(self) -> None:
        super().__init__(
            error_code="NO_PILL_DETECTED",
            message="이미지에서 알약 객체를 찾지 못했습니다.",
            status_code=422,
        )


class VisionTimeoutError(VisionServiceError):
    def __init__(self) -> None:
        super().__init__(
            error_code="VISION_TIMEOUT",
            message="Vision 모델 응답 시간이 초과되었습니다.",
            status_code=504,
        )


class VisionUpstreamError(VisionServiceError):
    def __init__(self, message: str = "Vision 모델 호출에 실패했습니다.") -> None:
        super().__init__(
            error_code="VISION_UPSTREAM_ERROR",
            message=message,
            status_code=502,
        )


class VisionService:
    _allowed_formats = {"JPEG", "PNG", "WEBP"}

    def __init__(self) -> None:
        self._openai_client: Any | None = None

    async def identify(
        self,
        *,
        image_bytes: bytes,
        content_type: str | None = None,
    ) -> VisionIdentifyResponse:
        if not image_bytes:
            raise VisionImageRequiredError()

        started_at = time.perf_counter()
        image = self._load_image(image_bytes=image_bytes, content_type=content_type)
        resized = self._resize_image_if_needed(image)
        boxes = self._detect_bboxes(resized)

        if not boxes:
            raise VisionNoPillDetectedError()

        detections: list[VisionDetection] = []
        for bbox in boxes[: max(1, config.VISION_MAX_DETECTIONS)]:
            x, y, w, h = bbox
            pad_x = max(1, int(round(w * 0.10)))
            pad_y = max(1, int(round(h * 0.10)))
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(resized.width, x + w + pad_x)
            y2 = min(resized.height, y + h + pad_y)
            if x2 <= x1 or y2 <= y1:
                x1, y1, x2, y2 = x, y, x + w, y + h
            crop = resized.crop((x1, y1, x2, y2))
            candidates = await self._identify_candidates(crop)
            detections.append(VisionDetection(bbox=[x, y, w, h], candidates=candidates))

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return VisionIdentifyResponse(
            detections=detections,
            latency_ms=latency_ms,
            disclaimer=config.VISION_DISCLAIMER,
        )

    def _load_image(self, *, image_bytes: bytes, content_type: str | None) -> Image.Image:
        if content_type and not content_type.startswith("image/"):
            raise VisionUnsupportedImageError()

        try:
            image = Image.open(io.BytesIO(image_bytes))
            image_format = (image.format or "").upper()
            if image_format not in self._allowed_formats:
                raise VisionUnsupportedImageError()
            image = ImageOps.exif_transpose(image).convert("RGB")
        except VisionServiceError:
            raise
        except UnidentifiedImageError as exc:
            raise VisionInvalidImageError from exc
        except Exception as exc:  # pragma: no cover - PIL 내부 예외 보호
            raise VisionInvalidImageError from exc
        return image

    def _resize_image_if_needed(self, image: Image.Image) -> Image.Image:
        max_side = max(image.size)
        if max_side <= config.VISION_MAX_IMAGE_SIDE:
            return image

        ratio = float(config.VISION_MAX_IMAGE_SIDE) / float(max_side)
        new_width = max(1, int(image.width * ratio))
        new_height = max(1, int(image.height * ratio))
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def _detect_bboxes(self, image: Image.Image) -> list[list[int]]:
        boxes = self._detect_bboxes_with_yolo(image)
        if boxes:
            return boxes

        if config.VISION_ENABLE_FULL_IMAGE_FALLBACK:
            return [[0, 0, image.width, image.height]]
        return []

    def _detect_bboxes_with_yolo(self, image: Image.Image) -> list[list[int]]:
        if config.VISION_BYPASS_YOLO:
            return []

        raw_boxes: list[dict[str, Any]] = []
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
                image.save(tmp, format="JPEG", quality=90)
                tmp.flush()

                child_code = (
                    "import json,sys\n"
                    "from ai_worker.vision.detector import predict_boxes\n"
                    "image_path=sys.argv[1]\n"
                    "conf=float(sys.argv[2])\n"
                    "model_path=sys.argv[3]\n"
                    "try:\n"
                    "    boxes=predict_boxes(image_path=image_path, conf_thres=conf, model_path=model_path)\n"
                    "    print(json.dumps({'ok': True, 'boxes': boxes}, ensure_ascii=False))\n"
                    "except Exception as exc:\n"
                    "    print(json.dumps({'ok': False, 'error': f'{type(exc).__name__}: {exc}'}, ensure_ascii=False))\n"
                )

                completed = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        child_code,
                        tmp.name,
                        str(config.VISION_DETECT_CONF_THRES),
                        str(config.VISION_DETECT_MODEL_PATH),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
        except subprocess.TimeoutExpired:
            default_logger.warning("[Vision] YOLO prediction timed out")
            return []
        except Exception as exc:
            default_logger.warning("[Vision] YOLO prediction failed: %s", exc)
            return []

        if completed.returncode != 0:
            default_logger.warning(
                "[Vision] YOLO subprocess failed (returncode=%s): %s",
                completed.returncode,
                (completed.stderr or "").strip()[-400:],
            )
            return []

        stdout = (completed.stdout or "").strip()
        if not stdout:
            default_logger.warning("[Vision] YOLO subprocess returned empty stdout")
            return []

        try:
            payload = json.loads(stdout.splitlines()[-1])
        except Exception:
            default_logger.warning("[Vision] YOLO subprocess output parse failed: %s", stdout[-400:])
            return []

        if not isinstance(payload, dict):
            return []
        if payload.get("ok") is not True:
            default_logger.warning("[Vision] YOLO subprocess error: %s", payload.get("error"))
            return []

        parsed_boxes = payload.get("boxes")
        if isinstance(parsed_boxes, list):
            raw_boxes = parsed_boxes

        normalized: list[tuple[float, list[int]]] = []
        for raw in raw_boxes:
            xyxy = raw.get("xyxy")
            if not isinstance(xyxy, list) or len(xyxy) != 4:
                continue

            x1, y1, x2, y2 = [float(v) for v in xyxy]
            x = max(0, min(image.width - 1, int(round(x1))))
            y = max(0, min(image.height - 1, int(round(y1))))
            right = max(0, min(image.width, int(round(x2))))
            bottom = max(0, min(image.height, int(round(y2))))
            w = right - x
            h = bottom - y
            if w <= 0 or h <= 0:
                continue

            conf = float(raw.get("confidence", 0.0))
            normalized.append((conf, [x, y, w, h]))

        normalized.sort(key=lambda item: item[0], reverse=True)
        return [bbox for _, bbox in normalized]

    async def _identify_candidates(self, crop: Image.Image) -> list[VisionCandidate]:
        image_base64 = self._encode_image_to_base64(crop)
        classifier_candidates = self._predict_classifier_candidates(crop)

        openai_candidates: list[VisionCandidate] = []
        if config.OPENAI_API_KEY:
            try:
                payload = await self._call_openai_with_retry(image_base64=image_base64)
                openai_candidates = self._extract_candidates(payload)
            except VisionServiceError as exc:
                if classifier_candidates:
                    default_logger.warning(
                        "[Vision] OpenAI failed (%s), fallback to classifier candidates",
                        exc.error_code,
                    )
                else:
                    raise

        candidates = self._merge_candidates(
            openai_candidates=openai_candidates,
            classifier_candidates=classifier_candidates,
        )

        if not candidates:
            candidates = [VisionCandidate(drug_name="식별불가", confidence=0.0)]
        return candidates

    def _encode_image_to_base64(self, image: Image.Image) -> str:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    async def _call_openai_with_retry(self, *, image_base64: str) -> dict[str, Any]:
        retries = max(0, config.VISION_OPENAI_RETRY_COUNT)
        backoff = max(0.0, float(config.VISION_OPENAI_BACKOFF_SEC))

        for attempt in range(retries + 1):
            try:
                return await self._call_openai_once(image_base64=image_base64)
            except VisionTimeoutError:
                if attempt >= retries:
                    raise
            except VisionUpstreamError as exc:
                if "OPENAI_API_KEY" in exc.message:
                    raise
                if attempt >= retries:
                    raise

            await asyncio.sleep(backoff * (2**attempt))

        raise VisionUpstreamError()

    async def _call_openai_once(self, *, image_base64: str) -> dict[str, Any]:
        if not config.OPENAI_API_KEY:
            raise VisionUpstreamError("OPENAI_API_KEY가 설정되어 있지 않습니다.")

        from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

        try:
            completion = await asyncio.wait_for(
                self._openai_client.chat.completions.create(
                    model=config.OPENAI_VISION_MODEL,
                    temperature=0,
                    response_format={"type": "json_object"},
                    max_tokens=config.VISION_OPENAI_MAX_TOKENS,
                    messages=[
                        {
                            "role": "system",
                            "content": ("너는 알약 이미지 분류 어시스턴트다. 반드시 JSON object만 반환하라."),
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "업로드된 알약 이미지를 분석해서 JSON으로 반환하라. "
                                        "반드시 candidates 배열을 포함하고, 각 요소는 "
                                        "{drug_name, confidence} 형식이어야 한다. "
                                        "confidence는 0~1 사이 숫자."
                                    ),
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_base64}",
                                    },
                                },
                            ],
                        },
                    ],
                ),
                timeout=float(config.VISION_OPENAI_TIMEOUT_SEC),
            )
        except (TimeoutError, APITimeoutError) as exc:
            raise VisionTimeoutError from exc
        except (APIConnectionError, APIStatusError, RateLimitError) as exc:
            raise VisionUpstreamError from exc
        except Exception as exc:
            raise VisionUpstreamError from exc

        content = self._extract_completion_content(completion)
        if not content:
            return {}

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            default_logger.warning("[Vision] OpenAI output was not JSON: %s", content)
            return {}

        if not isinstance(parsed, dict):
            return {}
        return parsed

    def _extract_completion_content(self, completion: Any) -> str:
        try:
            message_content = completion.choices[0].message.content
        except Exception:
            return ""

        if isinstance(message_content, str):
            return message_content.strip()

        if isinstance(message_content, list):
            chunks: list[str] = []
            for part in message_content:
                text_value = ""
                if isinstance(part, dict):
                    text_value = str(part.get("text", "")).strip()
                else:
                    text_value = str(getattr(part, "text", "")).strip()
                if text_value:
                    chunks.append(text_value)
            return " ".join(chunks).strip()

        return ""

    def _extract_candidates(self, payload: dict[str, Any]) -> list[VisionCandidate]:
        raw_candidates = payload.get("candidates")
        if not isinstance(raw_candidates, list):
            raw_candidates = []

        if not raw_candidates:
            drug_name = str(payload.get("drug_name", "")).strip()
            if drug_name:
                raw_candidates = [{"drug_name": drug_name, "confidence": payload.get("confidence", 0.0)}]

        deduped: dict[str, float] = {}
        for item in raw_candidates:
            if not isinstance(item, dict):
                continue
            drug_name = str(item.get("drug_name") or item.get("name") or "").strip()
            if not drug_name:
                continue

            confidence = self._normalize_confidence(item.get("confidence"))
            previous = deduped.get(drug_name)
            if previous is None or confidence > previous:
                deduped[drug_name] = confidence

        sorted_candidates = sorted(deduped.items(), key=lambda item: item[1], reverse=True)
        top_k = max(1, config.VISION_TOP_K)

        return [
            VisionCandidate(drug_name=drug_name, confidence=confidence)
            for drug_name, confidence in sorted_candidates[:top_k]
        ]

    def _predict_classifier_candidates(self, crop: Image.Image) -> list[VisionCandidate]:
        if not config.VISION_CLASSIFIER_ENABLED:
            return []

        model_path = Path(config.VISION_CLASSIFIER_MODEL_PATH)
        if not model_path.exists():
            default_logger.warning("[Vision] classifier model not found: %s", model_path)
            return []

        cls_outputs: list[dict[str, Any]] = []
        try:
            with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
                crop.save(tmp, format="PNG")
                tmp.flush()

                child_code = (
                    "import json,sys\n"
                    "from PIL import Image\n"
                    "from ai_worker.vision.classifier import predict_classes\n"
                    "image_path=sys.argv[1]\n"
                    "model_path=sys.argv[2]\n"
                    "labels_path=sys.argv[3]\n"
                    "top_k=int(sys.argv[4])\n"
                    "try:\n"
                    "    image=Image.open(image_path).convert('RGB')\n"
                    "    outputs=predict_classes(image=image, model_path=model_path, labels_path=labels_path, top_k=top_k)\n"
                    "    print(json.dumps({'ok': True, 'outputs': outputs}, ensure_ascii=False))\n"
                    "except Exception as exc:\n"
                    "    print(json.dumps({'ok': False, 'error': f'{type(exc).__name__}: {exc}'}, ensure_ascii=False))\n"
                )

                completed = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        child_code,
                        tmp.name,
                        str(model_path),
                        str(config.VISION_CLASSIFIER_LABELS_PATH or ""),
                        str(max(1, config.VISION_CLASSIFIER_TOP_K)),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
        except subprocess.TimeoutExpired:
            default_logger.warning("[Vision] classifier prediction timed out")
            return []
        except Exception as exc:
            default_logger.warning("[Vision] classifier prediction failed: %s", exc)
            return []

        if completed.returncode != 0:
            default_logger.warning(
                "[Vision] classifier subprocess failed (returncode=%s): %s",
                completed.returncode,
                (completed.stderr or "").strip()[-400:],
            )
            return []

        stdout = (completed.stdout or "").strip()
        if not stdout:
            default_logger.warning("[Vision] classifier subprocess returned empty stdout")
            return []

        try:
            payload = json.loads(stdout.splitlines()[-1])
        except Exception:
            default_logger.warning("[Vision] classifier subprocess output parse failed: %s", stdout[-400:])
            return []

        if not isinstance(payload, dict):
            return []
        if payload.get("ok") is not True:
            default_logger.warning("[Vision] classifier subprocess error: %s", payload.get("error"))
            return []

        parsed_outputs = payload.get("outputs")
        if isinstance(parsed_outputs, list):
            cls_outputs = parsed_outputs

        candidates: list[VisionCandidate] = []
        for output in cls_outputs:
            class_name = str(output.get("class_name", "")).strip()
            if not class_name:
                continue
            confidence = self._normalize_confidence(output.get("confidence"))
            candidates.append(VisionCandidate(drug_name=class_name, confidence=confidence))
        return candidates

    def _merge_candidates(
        self,
        *,
        openai_candidates: list[VisionCandidate],
        classifier_candidates: list[VisionCandidate],
    ) -> list[VisionCandidate]:
        if not classifier_candidates:
            return openai_candidates

        weight = min(1.0, max(0.0, float(config.VISION_CLASSIFIER_WEIGHT)))
        merged: dict[str, float] = {}

        for candidate in openai_candidates:
            merged[candidate.drug_name] = max(merged.get(candidate.drug_name, 0.0), candidate.confidence)

        for candidate in classifier_candidates:
            existing = merged.get(candidate.drug_name)
            if existing is None:
                merged[candidate.drug_name] = candidate.confidence
            else:
                merged[candidate.drug_name] = ((1.0 - weight) * existing) + (weight * candidate.confidence)

        top_k = max(1, config.VISION_TOP_K)
        sorted_candidates = sorted(merged.items(), key=lambda item: item[1], reverse=True)
        return [
            VisionCandidate(drug_name=drug_name, confidence=confidence)
            for drug_name, confidence in sorted_candidates[:top_k]
        ]

    def _normalize_confidence(self, value: Any) -> float:
        parsed = 0.0
        if isinstance(value, str):
            try:
                parsed = float(value.strip().replace("%", ""))
            except ValueError:
                parsed = 0.0
        elif isinstance(value, (int, float)):
            parsed = float(value)

        if parsed > 1.0 and parsed <= 100.0:
            parsed = parsed / 100.0

        return min(1.0, max(0.0, parsed))
