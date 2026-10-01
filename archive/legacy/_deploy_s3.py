import boto3
import mimetypes
import pathlib

BUCKET = "authrex-demo-26697"
DIST   = r"D:\xzashr.ai Files\clincase-workspace\ClinCase\frontend\dist"

s3 = boto3.client("s3", region_name="us-east-1")

# Delete all existing objects
resp = s3.list_objects_v2(Bucket=BUCKET)
if resp.get("Contents"):
    keys = [{"Key": o["Key"]} for o in resp["Contents"]]
    s3.delete_objects(Bucket=BUCKET, Delete={"Objects": keys})
    print(f"Deleted {len(keys)} old objects")

# Upload every file from dist/
uploaded = 0
for path in pathlib.Path(DIST).rglob("*"):
    if not path.is_file():
        continue
    key = path.relative_to(DIST).as_posix()
    ct, _ = mimetypes.guess_type(str(path))
    ct = ct or "application/octet-stream"
    extra = {"ContentType": ct}
    if path.suffix in (".js", ".css", ".html"):
        extra["CacheControl"] = "no-cache, no-store, must-revalidate"
    s3.upload_file(str(path), BUCKET, key, ExtraArgs=extra)
    print(f"  {key}")
    uploaded += 1

print(f"\nDone — {uploaded} files live at http://{BUCKET}.s3-website-us-east-1.amazonaws.com")
