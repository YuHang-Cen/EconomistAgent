export interface Article {
  id: string;
  title: string;
  author: string;
  topic: string;
  date: string;
  mainSkill?: string;
  subSkills?: string[];
  content: {
    type: 'paragraph' | 'heading';
    text: string;
  }[];
}

export const ARTICLES: Record<string, Article> = {
  'as-3': {
    id: 'as-3',
    title: 'The Invisible Hand in the Digital Age: An Inquiry into Algorithmic Equilibrium',
    author: 'Adam Smith (AI Simulation)',
    topic: 'Digital Economic Theory',
    date: 'October 24, 2023',
    mainSkill: 'Systemic Crisis Analysis',
    subSkills: ['Market Equilibrium Modeling', 'Institutional Framework Evolution', 'Behavioral Incentive Mapping'],
    content: [
      {
        type: 'paragraph',
        text: 'It is not from the benevolence of the digital architect, the platform provider, or the content creator that we expect our personalized experiences, but from their regard to their own interest. In the vast marketplace of data, the individual is led by an invisible hand—now manifested as a silicon-based algorithm—to promote an end which was no part of his intention.'
      },
      {
        type: 'heading',
        text: 'I. The Division of Computational Labor'
      },
      {
        type: 'paragraph',
        text: 'As the wealth of nations once depended upon the pin factory\'s efficiency, the wealth of networks now rests upon the atomization of processing power. We observe a new division of labor, where the human intellect provides the raw aesthetic intuition, while the machine executes the repetitive cycles of predictive analysis. This synergy increases the universal opulence of information, extending even to the lowest ranks of the connected populace.'
      }
    ]
  }
};
