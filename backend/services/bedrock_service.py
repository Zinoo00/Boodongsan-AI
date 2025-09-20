import json
import boto3
from botocore.exceptions import ClientError
import logging
from core.config import settings

logger = logging.getLogger(__name__)

class BedrockService:
    def __init__(self):
        """AWS Bedrock 클라이언트 초기화"""
        try:
            # bedrock-runtime 클라이언트 (모델 호출용)
            self.runtime_client = boto3.client(
                'bedrock-runtime',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY.get_secret_value(),
                region_name=settings.AWS_REGION
            )
            
            # bedrock 클라이언트 (모델 목록 조회용)
            self.bedrock_client = boto3.client(
                'bedrock',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY.get_secret_value(),
                region_name=settings.AWS_REGION
            )
            
            self.model_id = settings.BEDROCK_MODEL_ID
            
            logger.info("AWS Bedrock 클라이언트가 성공적으로 초기화되었습니다.")
            
        except Exception as e:
            logger.error(f"Bedrock 클라이언트 초기화 실패: {e}")
            raise
    
    def test_connection(self):
        """Bedrock 연결 테스트"""
        try:
            # bedrock 클라이언트로 모델 목록 조회
            response = self.bedrock_client.list_foundation_models()
            logger.info(f"Bedrock 모델 목록: {response}")
            return True
        except ClientError as e:
            logger.error(f"Bedrock 연결 테스트 실패: {e}")
            return False
        except Exception as e:
            logger.error(f"예상치 못한 오류: {e}")
            return False
    
    def send_message(self, message: str) -> str:
        """간단한 메시지 전송 (비스트리밍)"""
        try:
            # 요청 페이로드 구성
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "temperature": 0.7,
                "messages": [
                    {
                        "role": "user",
                        "content": message
                    }
                ]
            }
            
            # Bedrock API 호출 (runtime 클라이언트 사용)
            response = self.runtime_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType="application/json"
            )
            
            # 응답 파싱
            response_body = json.loads(response['body'].read())
            content = response_body['content'][0]['text']
            
            return content
            
        except ClientError as e:
            logger.error(f"Bedrock API 오류: {e}")
            return f"API 오류가 발생했습니다: {str(e)}"
        except Exception as e:
            logger.error(f"예상치 못한 오류: {e}")
            return f"서버 오류가 발생했습니다: {str(e)}" 