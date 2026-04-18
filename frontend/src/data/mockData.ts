export const AUTHORS = [
  {
    id: 'adam-smith',
    name: 'Adam Smith',
    school: 'Classical School',
    manuscriptsCount: 12,
    avatarUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuDQDQK3nkRMxZlX0rIsX7IHKStkOcyaC_-8e0e7itIXXL8g-XzzXcG6Wt-H6upqizj2iHrcli243TJnSH_8Ym089mZqVT0mD07KgXFZDK4HEhEV9mPb2axiH5GDLgw99EpEY4Ln7U6z20s-r0-DxHynGTZPpJpOa_Eu3jEHji69ROyvCYhs8hJ3MZdfmQ4SXqBUXieGc5VrqOxTUbb6Z9B879a5mWHQGQukz5Eexp2OmawlPqoGaKhn92TuEKcTTtKAXXH_wGahvzY',
    manuscripts: [
      { id: 'm1', title: 'The Wealth of Nations (1776)', uploadDate: 'Oct 12, 2023', status: 'indexed' },
      { id: 'm2', title: 'The Theory of Moral Sentiments', uploadDate: 'Nov 04, 2023', status: 'indexed' },
      { id: 'm3', title: 'Lectures on Jurisprudence', uploadDate: 'Jan 22, 2024', status: 'pending' },
    ],
    books: [
      {
        id: 'won',
        title: 'The Wealth of Nations',
        chapters: [
          { id: 'won-c1', title: 'Chapter 1: The Division of Labour' },
          { id: 'won-c2', title: 'Chapter 2: The Principle of Exchange' },
          { id: 'won-c3', title: 'Chapter 3: Limited by Extent of Market' }
        ]
      },
      {
        id: 'tms',
        title: 'The Theory of Moral Sentiments',
        chapters: [
          { id: 'tms-c1', title: 'Chapter 1: Of Sympathy' },
          { id: 'tms-c2', title: 'Chapter 2: Of the Pleasure of Mutual Sympathy' }
        ]
      }
    ]
  },
  {
    id: 'john-keynes',
    name: 'John M. Keynes',
    school: 'Keynesian School',
    manuscriptsCount: 8,
    avatarUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCqC0W7UNRPxq6BO8iNp74lRN5vGZ67IJuwTgvvreBgcU_jXBvgPw2QuyjcsbFkh7pWVnNZfocE3DYKCHdau3ggmPhgwFLVBF3z5iOvhI-SHUsZd6hyvPngsKsR3lF8F5t4lzjO39PmxcDXThQNQqRvxfOSqO3809tI3tIow9u6ylg0ffDX4nd31Br5CtpZ5mqVDra9Vng2l5yEbEMQk7X1J9QI5X9tcrkZTwJ5bTg3OjKCwXTppgSlFGHgf21VnAUxjwA1jRyUmGo',
    manuscripts: [
      { id: 'm4', title: 'General Theory of Employment, Interest and Money', uploadDate: 'Feb 01, 2024', status: 'indexed' },
      { id: 'm5', title: 'A Treatise on Money', uploadDate: 'Feb 15, 2024', status: 'pending' },
    ],
    books: [
      {
        id: 'gt',
        title: 'General Theory of Employment',
        chapters: [
          { id: 'gt-c1', title: 'Chapter 1: The General Theory' },
          { id: 'gt-c2', title: 'Chapter 2: The Postulates of the Classical Economics' }
        ]
      }
    ]
  },
  {
    id: 'david-ricardo',
    name: 'David Ricardo',
    school: 'Classical School',
    manuscriptsCount: 4,
    initials: 'DR',
    manuscripts: [
      { id: 'm6', title: 'On the Principles of Political Economy and Taxation', uploadDate: 'Mar 10, 2024', status: 'indexed' }
    ],
    books: [
      {
        id: 'ppe',
        title: 'Principles of Political Economy',
        chapters: [
          { id: 'ppe-c1', title: 'Chapter 1: On Value' },
          { id: 'ppe-c2', title: 'Chapter 2: On Rent' }
        ]
      }
    ]
  },
  {
    id: 'milton-friedman',
    name: 'Milton Friedman',
    school: 'Monetarist School',
    manuscriptsCount: 6,
    initials: 'MF',
    manuscripts: [
      { id: 'm7', title: 'Capitalism and Freedom', uploadDate: 'Apr 05, 2024', status: 'indexed' }
    ],
    books: [
      {
        id: 'cf',
        title: 'Capitalism and Freedom',
        chapters: [
          { id: 'cf-c1', title: 'Chapter 1: The Relation between Economic Freedom and Political Freedom' }
        ]
      }
    ]
  },
  {
    id: 'joan-robinson',
    name: 'Joan Robinson',
    school: 'Post-Keynesian School',
    manuscriptsCount: 5,
    initials: 'JR',
    manuscripts: [
      { id: 'm8', title: 'The Economics of Imperfect Competition', uploadDate: 'May 12, 2024', status: 'indexed' }
    ],
    books: [
      {
        id: 'eic',
        title: 'Economics of Imperfect Competition',
        chapters: [
          { id: 'eic-c1', title: 'Chapter 1: The Technique' }
        ]
      }
    ]
  }
];

export const HISTORY_DATA = [
  {
    authorId: 'adam-smith',
    items: [
      { id: 'as-1', title: 'Theory of Moral Sentiments Analysis' },
      { id: 'as-2', title: 'The Wealth of Nations Analysis' },
      { id: 'as-3', title: 'Invisible Hand in Markets' },
    ]
  },
  {
    authorId: 'john-keynes',
    items: [
      { id: 'jmk-1', title: 'General Theory of Employment' },
      { id: 'jmk-2', title: 'Macroeconomic Aggregates' },
    ]
  },
  {
    authorId: 'joan-robinson',
    items: [
      { id: 'jr-1', title: 'Imperfect Competition Study' },
    ]
  },
  {
    authorId: 'milton-friedman',
    items: [
      { id: 'mf-1', title: 'Monetary History of US' },
    ]
  }
];
