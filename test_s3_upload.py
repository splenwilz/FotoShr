import boto3
import os
from dotenv import load_dotenv
import uuid

# Load environment variables
load_dotenv()

def test_s3_upload():
    try:
        # Get S3 configuration from environment variables
        aws_s3_bucket = os.environ.get('AWS_S3_BUCKET')
        aws_region = os.environ.get('AWS_REGION')
        
        print(f"Testing S3 upload to bucket: {aws_s3_bucket} in region: {aws_region}")
        
        # Create a boto3 S3 client with the handsondev profile
        session = boto3.Session(profile_name='handsondev')
        s3_client = session.client('s3', region_name=aws_region)
        
        # Check if client is initialized
        print("S3 client initialized successfully")
        
        # Create a small test file
        test_filename = "test_upload.txt"
        with open(test_filename, "w") as f:
            f.write("This is a test file for S3 upload")
        
        # Upload the file to S3
        object_name = f"{uuid.uuid4().hex}_{test_filename}"
        
        print(f"Uploading {test_filename} to S3 as {object_name}...")
        
        with open(test_filename, "rb") as file_data:
            s3_client.upload_fileobj(file_data, aws_s3_bucket, object_name)
        
        # Generate a pre-signed URL
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': aws_s3_bucket, 'Key': object_name},
            ExpiresIn=3600
        )
        
        print(f"Upload successful!")
        print(f"File accessible at: {url}")
        
        # Clean up the local test file
        os.remove(test_filename)
        
        return True, object_name
        
    except Exception as e:
        print(f"Error in S3 upload test: {str(e)}")
        return False, None

if __name__ == "__main__":
    success, object_name = test_s3_upload()
    
    if success:
        print("\nS3 integration is working correctly!")
        
        # List bucket contents to verify
        session = boto3.Session(profile_name='handsondev')
        s3 = session.client('s3', region_name=os.environ.get('AWS_REGION'))
        print("\nBucket contents:")
        response = s3.list_objects_v2(Bucket=os.environ.get('AWS_S3_BUCKET'))
        
        if 'Contents' in response:
            for obj in response['Contents']:
                print(f" - {obj['Key']} ({obj['Size']} bytes)")
        else:
            print("No objects found in bucket (this should not happen since we just uploaded one)")
    else:
        print("\nS3 integration test failed!") 