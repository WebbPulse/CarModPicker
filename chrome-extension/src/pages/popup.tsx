import { useEffect, useState } from 'react';
import LoginScreen from '../components/popup/LoginScreen';
import MainScreen from '../components/popup/MainScreen';
import PartDialog from '../components/popup/PartDialog';
import type { User, ScrapedProductData } from '../types';

function Popup() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showPartDialog, setShowPartDialog] = useState(false);
  const [scrapedData, setScrapedData] = useState<ScrapedProductData | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ message: string; type: 'info' | 'success' | 'error' } | null>(null);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  // Dynamically resize popup window based on dialog state
  useEffect(() => {
    const body = document.body;
    if (showPartDialog) {
      body.style.width = '800px';
    } else {
      body.style.width = '400px';
    }
  }, [showPartDialog]);

  const checkAuthStatus = async () => {
    try {
      const response = (await sendMessage({
        action: 'getCurrentUser',
      })) as { success: boolean; data?: User };
      
      if (response.success && response.data) {
        setUser(response.data);
      } else {
        setUser(null);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogin = (userData: User) => {
    setUser(userData);
  };

  const handleLogout = async () => {
    await sendMessage({ action: 'logout' });
    setUser(null);
  };

  const handleScrape = async () => {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id) {
        showStatus('No active tab found', 'error');
        return;
      }

      chrome.tabs.sendMessage(
        tab.id,
        { action: 'scrapePage' },
        (response: { success: boolean; data: ScrapedProductData } | undefined) => {
          if (chrome.runtime.lastError) {
            showStatus(
              'Failed to scrape page data. Make sure you are on a product page and refresh if needed.',
              'error'
            );
            return;
          }
          if (response && response.success && response.data) {
            setScrapedData(response.data);
            setShowPartDialog(true);
          } else {
            showStatus('Failed to scrape page data. Make sure you are on a product page.', 'error');
          }
        }
      );
    } catch (error) {
      showStatus(
        'Error scraping page: ' + (error instanceof Error ? error.message : 'Unknown error'),
        'error'
      );
    }
  };

  const showStatus = (message: string, type: 'info' | 'success' | 'error') => {
    setStatusMessage({ message, type });
    if (type === 'success') {
      setTimeout(() => {
        setStatusMessage(null);
      }, 3000);
    }
  };

  const handlePartCreated = () => {
    setShowPartDialog(false);
    setScrapedData(null);
    showStatus('Part created successfully!', 'success');
  };

  type SendMessageParams = {
    action: string;
    username?: string;
    password?: string;
    partData?: unknown;
    imageUrl?: string;
    limit?: number;
    searchTerm?: string;
  };

  const sendMessage = (message: SendMessageParams): Promise<unknown> => {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(message, (response: unknown) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(response);
        }
      });
    });
  };

  if (isLoading) {
    return (
      <div className="w-full min-h-[200px] flex items-center justify-center">
        <div className="text-white/60">Loading...</div>
      </div>
    );
  }

  // Dynamically size the popup based on whether we're showing the dialog
  const containerClasses = showPartDialog
    ? "w-full min-h-[600px] max-h-[600px] overflow-y-auto"
    : "w-full overflow-y-auto";

  return (
    <div className={containerClasses}>
      {!user ? (
        <LoginScreen onLogin={handleLogin} sendMessage={sendMessage} />
      ) : (
        <MainScreen
          user={user}
          onLogout={handleLogout}
          onScrape={handleScrape}
          statusMessage={statusMessage}
        />
      )}
      
      {showPartDialog && scrapedData && (
        <PartDialog
          scrapedData={scrapedData}
          onClose={() => {
            setShowPartDialog(false);
            setScrapedData(null);
          }}
          onPartCreated={handlePartCreated}
          sendMessage={sendMessage}
        />
      )}
    </div>
  );
}

export default Popup;
