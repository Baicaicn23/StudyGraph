"use client";

import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

// Markdown 渲染：支持表格/任务列表（GFM）、数学公式（KaTeX）、代码高亮。
export default function Markdown({ content }: { content: string }) {
  return (
    <div className="prose prose-zinc max-w-none prose-pre:my-2 prose-pre:bg-zinc-900 prose-pre:text-zinc-100">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, rehypeHighlight]}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
