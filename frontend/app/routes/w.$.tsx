import {
  redirect,
} from "@remix-run/react";
import type { LoaderFunctionArgs } from "@remix-run/node";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const url = new URL(request.url);
  url.protocol = "https";
  url.host = "ja.m.wikipedia.org";
  url.port = "";
  return redirect(url.toString());
};
