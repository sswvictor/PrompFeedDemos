import { getPromptFeedBlockComponent } from './blockRegistry';

export default function PromptFeedRenderer({ response }) {
  if (!response?.blocks?.length) return null;

  return (
    <div className="space-y-4">
      {response.blocks.map((block, index) => {
        const BlockComponent = getPromptFeedBlockComponent(block.type);
        return <BlockComponent key={`${block.type}-${index}`} block={block} response={response} />;
      })}
    </div>
  );
}
