from pathlib import Path
import mimetypes
import streamlit as st
import truststore
from supabase import create_client

truststore.inject_into_ssl()
BUCKET = "exam-files"

sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
bucket = sb.storage.from_(BUCKET)

def remote(v):
    return bool(v) and str(v).lower().startswith(("http://","https://"))

def upload(local_path, object_path):
    p=Path(local_path)
    if not p.exists():
        print("MISSING:", local_path)
        return None
    content_type=mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    bucket.upload(
        path=object_path,
        file=p.read_bytes(),
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return bucket.get_public_url(object_path)

def main():
    papers=sb.table("papers").select("*").execute().data
    for paper in papers:
        pid=paper["id"]

        # Original source: legacy DB stores filename only, so reconstruct from paper folder.
        filename=paper.get("filename")
        if filename and not remote(filename):
            local=Path("papers")/paper["folder"]/filename
            url=upload(local, f"papers/{pid}/original/{Path(filename).name}")
            if url:
                sb.table("papers").update({"filename":url}).eq("id",pid).execute()
                print("paper original:", pid)

        passages=sb.table("passages").select("id,image").eq("paper_id",pid).execute().data
        for row in passages:
            value=row.get("image")
            if value and not remote(value):
                ext=Path(value).suffix or ".png"
                url=upload(value, f"papers/{pid}/passages/passage_{row['id']}{ext}")
                if url:
                    sb.table("passages").update({"image":url}).eq("id",row["id"]).execute()
                    print("passage:", row["id"])

        questions=sb.table("questions").select("id,question_number,question_image").eq("paper_id",pid).execute().data
        for row in questions:
            value=row.get("question_image")
            if value and not remote(value):
                ext=Path(value).suffix or ".png"
                url=upload(value, f"papers/{pid}/questions/q{row['question_number']}{ext}")
                if url:
                    sb.table("questions").update({"question_image":url}).eq("id",row["id"]).execute()
                    print("question:", row["id"])

    print("Storage migration completed.")

if __name__=="__main__":
    main()
