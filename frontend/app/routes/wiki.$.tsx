import {
  MetaFunction,
  redirect,
  useLoaderData,
} from "@remix-run/react";
import type { LoaderFunctionArgs } from "@remix-run/node";
import classes from "../css/wiki.module.css";
import { fileStorage, s3Storage } from "~/storage";

function originalWikiLink(page: string) {
  return `https://ja.m.wikipedia.org/wiki/${encodeURIComponent(page)}`;
}

export const loader = async ({ params }: LoaderFunctionArgs) => {
  const page = params["*"];
  if (!page) {
    throw new Response(null, {
      status: 404,
      statusText: "Not Found",
    });
  }
  const storage = process.env.STORAGE_BACKEND === 's3' ? s3Storage : fileStorage;
  // TODO: prevent path traversal
  const jsonData = await storage.read(`${page.replaceAll('/', '__')}.json`);
  if (!jsonData) {
    return redirect(originalWikiLink(page));
  }
  const data = JSON.parse(jsonData);
  if (data.redirect) {
    let redirectUrl = `/wiki/${encodeURIComponent(data.redirect.to)}`;
    if (data.redirect.tofragment) {
      redirectUrl += `#${encodeURIComponent(data.redirect.tofragment)}`;
    }
    return redirect(redirectUrl);
  }
  return data;
};

export const meta: MetaFunction<typeof loader> = ({
  data,
}) => {
  return [{ title: `${data.title} - jako` }];
};

export default function WikiPage() {
  const data = useLoaderData<typeof loader>();
  return (<>
    <div className={classes.notice}>
      <strong>🌐 이 문서는 일본어 위키백과에서 기계 번역 되었습니다.</strong>{' '}
      정확한 내용이 필요한 경우, <a href={originalWikiLink(data.original_title)} target="_blank">원문</a>을 확인해 주세요.
      <div className={classes.meta}>
        <span className={classes.metaItem}>
          최종 수정일: {new Intl.DateTimeFormat('ko', {dateStyle: 'medium', timeZone: 'Asia/Seoul'}).format(new Date(data.last_rev_timestamp))} (원문 조회시점 기준)
        </span>
        <span className={classes.metaItem}>
          저작권 정보: <a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ko" target="_blank">CC BY-SA 4.0</a>
        </span>
        <span className={classes.poweredBy}>
          <a href="https://github.com/dittos/jako">🇯🇵 &rsaquo; 🇰🇷 jako</a> 제공
        </span>
      </div>
    </div>

    <div className={classes.header}>
      <h1 className={classes.headerTitle}>{data.title}</h1>
    </div>

    <div className={`content ${classes.content}`}>
      <div
        id="mw-content-text"
        className="mw-body-content"
        dangerouslySetInnerHTML={{ __html: data.html }}
      />
    </div>
  </>);
}
