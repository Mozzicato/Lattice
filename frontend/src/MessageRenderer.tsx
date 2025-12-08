import React from 'react';
import ReactMarkdown from 'react-markdown';
import { InlineMath, BlockMath } from 'react-katex';
import 'katex/dist/katex.min.css';

interface MessageRendererProps {
  content: string;
}

const MessageRenderer: React.FC<MessageRendererProps> = ({ content }) => {
  // Parse content and split into text and math segments
  const renderContent = (text: string) => {
    const segments: React.ReactNode[] = [];
    let remaining = text;
    let key = 0;

    while (remaining.length > 0) {
      // Check for block math first ($$...$$)
      const blockMatch = remaining.match(/\$\$([\s\S]*?)\$\$/);
      // Check for inline math ($...$)
      const inlineMatch = remaining.match(/\$([^$\n]+?)\$/);

      if (blockMatch && (!inlineMatch || remaining.indexOf(blockMatch[0]) <= remaining.indexOf(inlineMatch[0]))) {
        // Block math found first
        const index = remaining.indexOf(blockMatch[0]);
        if (index > 0) {
          // Add text before the math
          segments.push(
            <ReactMarkdown key={key++}>{remaining.substring(0, index)}</ReactMarkdown>
          );
        }
        try {
          segments.push(
            <BlockMath key={key++} math={blockMatch[1].trim()} />
          );
        } catch (e) {
          // If KaTeX fails, show the raw LaTeX
          segments.push(<pre key={key++} className="math-fallback">{blockMatch[0]}</pre>);
        }
        remaining = remaining.substring(index + blockMatch[0].length);
      } else if (inlineMatch) {
        // Inline math found
        const index = remaining.indexOf(inlineMatch[0]);
        if (index > 0) {
          // Add text before the math
          segments.push(
            <ReactMarkdown key={key++}>{remaining.substring(0, index)}</ReactMarkdown>
          );
        }
        try {
          segments.push(
            <InlineMath key={key++} math={inlineMatch[1].trim()} />
          );
        } catch (e) {
          // If KaTeX fails, show the raw LaTeX
          segments.push(<code key={key++} className="math-fallback">{inlineMatch[0]}</code>);
        }
        remaining = remaining.substring(index + inlineMatch[0].length);
      } else {
        // No more math, add remaining text
        segments.push(
          <ReactMarkdown key={key++}>{remaining}</ReactMarkdown>
        );
        break;
      }
    }

    return segments;
  };

  return <div className="message-renderer">{renderContent(content)}</div>;
};

export default MessageRenderer;
