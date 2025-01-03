import { GetObjectCommand, NoSuchKey, S3Client } from "@aws-sdk/client-s3";
import fs from "fs/promises";
import path from "path";

export const fileStorage = {
  async read(key: string): Promise<string | null> {
    try {
      return await fs.readFile(path.join(process.env.STORAGE_FILE_DIR!, key), "utf-8");
    } catch (e: any) {
      if (e.code === "ENOENT") {
        return null;
      } else {
        throw e;
      }
    }
  }
}

const client = new S3Client();

export const s3Storage = {
  async read(key: string): Promise<string | null> {
    try {
      const response = await client.send(
        new GetObjectCommand({
          Bucket: process.env.S3_BUCKET_NAME,
          Key: key,
        }),
      );
      // The Body object also has 'transformToByteArray' and 'transformToWebStream' methods.
      return await response.Body?.transformToString() ?? null;
    } catch (caught: any) {
      if (caught instanceof NoSuchKey) {
        return null;
      } else {
        throw caught;
      }
    }
  }
}
