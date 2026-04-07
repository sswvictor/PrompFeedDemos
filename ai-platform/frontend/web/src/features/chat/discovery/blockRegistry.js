import {
  AvailabilityPickerBlock,
  CTAButtonRowBlock,
  ConversationalFollowUpBlock,
  HeroCardBlock,
  ProfileMemoryCardBlock,
  ProviderResultsBlock,
  SearchSummaryCardBlock,
  UnsupportedBlock,
} from './promptBlocks';

export const promptFeedBlockRegistry = {
  HeroCard: HeroCardBlock,
  SearchSummaryCard: SearchSummaryCardBlock,
  ProviderResults: ProviderResultsBlock,
  AvailabilityPicker: AvailabilityPickerBlock,
  ProfileMemoryCard: ProfileMemoryCardBlock,
  CTAButtonRow: CTAButtonRowBlock,
  ConversationalFollowUp: ConversationalFollowUpBlock,
};

export function getPromptFeedBlockComponent(type) {
  return promptFeedBlockRegistry[type] || UnsupportedBlock;
}
