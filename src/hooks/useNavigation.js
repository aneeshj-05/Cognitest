import { useState } from 'react';

/**
 * Custom hook for managing page navigation and history
 */
export const useNavigation = (initialPage = 'home') => {
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [history, setHistory] = useState([initialPage]);

  const navigateTo = (page) => {
    setHistory(prev => [...prev, page]);
    setCurrentPage(page);
    window.scrollTo(0, 0);
  };

  const goBack = () => {
    if (history.length > 1) {
      const newHistory = [...history];
      newHistory.pop();
      const prevPage = newHistory[newHistory.length - 1];
      setHistory(newHistory);
      setCurrentPage(prevPage);
    } else {
      setCurrentPage(initialPage);
    }
  };

  return { currentPage, navigateTo, goBack };
};
