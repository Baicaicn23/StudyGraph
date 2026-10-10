import { redirect } from "next/navigation";

/**
 * 错题本已并入「错题练习」页（/practice）的第一个 tab。
 * 旧链接保持可用：直接重定向过去。
 */
export default function MistakesRedirect() {
  redirect("/practice?tab=mistakes");
}
