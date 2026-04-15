export interface Chapter {
  id: string;
  title: string;
  content?: string;
}

export interface Book {
  id: string;
  title: string;
  chapters: Chapter[];
}

export interface Manuscript {
  id: string;
  title: string;
  uploadDate: string;
  status: 'indexed' | 'pending';
}

export interface Author {
  id: string;
  name: string;
  school: string;
  manuscriptsCount: number;
  avatarUrl?: string;
  initials?: string;
  manuscripts: Manuscript[];
  books: Book[];
}
