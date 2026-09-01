import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useAuth } from '../hooks/useAuth';
import { useTranslation } from 'react-i18next';
import { useEffect } from 'react';
import {
  HomeIcon,
  Cog6ToothIcon,
  DocumentIcon,
  CreditCardIcon,
  GlobeAltIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';

const navigation = [
  { name: 'nav.dashboard', href: '/dashboard', icon: HomeIcon },
  { name: 'nav.settings', href: '/settings', icon: Cog6ToothIcon },
  { name: 'nav.about', href: '/about-dev', icon: DocumentIcon },
  { name: 'nav.account', href: '/account', icon: CreditCardIcon },
];

const adminNavigation = [
  { name: 'nav.admin', href: '/admin', icon: ShieldCheckIcon },
];

const languages = [
  { code: 'en', name: 'English', flag: '🇺🇸', rtl: false },
  { code: 'es', name: 'Español', flag: '🇪🇸', rtl: false },
  { code: 'fr', name: 'Français', flag: '🇫🇷', rtl: false },
  { code: 'ar', name: 'العربية', flag: '🇸🇦', rtl: true },
];

export default function Layout() {
  const { user, isAdmin } = useAuthStore();
  const { logout: doLogout } = useAuth();
  const { t, i18n } = useTranslation();
  const location = useLocation();

  // Update document direction for RTL languages
  useEffect(() => {
    const lang = languages.find(l => l.code === i18n.language);
    document.documentElement.dir = lang?.rtl ? 'rtl' : 'ltr';
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);

  const handleLanguageChange = (code: string) => {
    i18n.changeLanguage(code);
  };

  const isAdminRoute = location.pathname.startsWith('/admin');

  const currentNav = isAdminRoute ? adminNavigation : navigation;

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <NavLink to={isAdminRoute ? '/admin' : '/dashboard'} className="flex items-center space-x-2">
                <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                  <HomeIcon className="w-5 h-5 text-white" />
                </div>
                <span className="text-xl font-bold text-gray-900">OminiVoice</span>
              </NavLink>
              <div className="hidden md:ml-8 md:flex md:space-x-4">
                {currentNav.map((item) => (
                  <NavLink
                    key={item.name}
                    to={item.href}
                    className={({ isActive }) =>
                      `flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? 'bg-primary-50 text-primary-700'
                          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                      }`
                    }
                  >
                    <item.icon className="w-5 h-5 mr-2" />
                    {t(item.name)}
                  </NavLink>
                ))}
              </div>
            </div>
            <div className="flex items-center space-x-4">
              {/* Language Selector */}
              <div className="relative hidden sm:block">
                <select
                  value={i18n.language}
                  onChange={(e) => handleLanguageChange(e.target.value)}
                  className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5 text-sm font-medium text-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent appearance-none pr-8 cursor-pointer"
                  aria-label={t('accessibility.languageSelector')}
                >
                  {languages.map((lang) => (
                    <option key={lang.code} value={lang.code}>
                      {lang.flag} {lang.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="hidden sm:block relative">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center">
                    <span className="text-primary-700 font-medium text-sm">
                      {user?.email?.charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <span className="text-sm font-medium text-gray-700">{user?.email}</span>
                </div>
              </div>
              <button
                onClick={doLogout}
                className="text-sm text-gray-600 hover:text-gray-900 font-medium"
              >
                {t('common.logout')}
              </button>
            </div>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}