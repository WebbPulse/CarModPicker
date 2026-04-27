import { useState } from 'react';
import { BsTools } from 'react-icons/bs';
import {
  FaBars,
  FaBug,
  FaChrome,
  FaCoffee,
  FaCogs,
  FaSearch,
  FaSignOutAlt,
  FaTimes,
  FaUser,
} from 'react-icons/fa';
import { GiRaceCar } from 'react-icons/gi';
import { Link } from 'react-router-dom';
import { CHROME_EXTENSION_STORE_URL } from '../../../constants';
import { useAuth } from '../../../hooks/useAuth';
import { Button } from '../../ui/button';
import Spinner from '../../ui/spinner';

function Header() {
  const { isAuthenticated, logout, isLoading, user } = useAuth();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  const handleLogout = () => {
    void logout();
    setIsMobileMenuOpen(false);
  };

  return (
    <header className="w-full">
      {/* Background with gradient */}
      <div className="absolute inset-0 bg-linear-to-r from-card via-muted to-card opacity-95 backdrop-blur-md"></div>

      {/* Main Header Content */}
      <div className="relative">
        {/* Top Tier - Logo and Auth */}
        <div className="container mx-auto px-4 py-3">
          <div className="flex justify-between items-center">
            {/* Logo */}
            <Link
              to="/"
              className="flex items-center space-x-2 group animate-slideInLeft"
            >
              <div className="w-10 h-10 bg-linear-to-br from-primary to-primary rounded-xl flex items-center justify-center shadow-lg group-hover:shadow-primary/25 transition-all duration-300 group-hover:scale-110">
                <GiRaceCar className="text-white text-xl" />
              </div>
              <span className="text-2xl font-bold bg-linear-to-r from-white to-foreground bg-clip-text text-transparent">
                CarModPicker
              </span>
            </Link>

            {/* Desktop Auth Section */}
            <div className="hidden md:flex items-center space-x-4">
              {isLoading ? (
                <div className="flex items-center space-x-2">
                  <Spinner inline />
                  <span className="text-sm text-muted-foreground">Loading...</span>
                </div>
              ) : isAuthenticated ? (
                <div className="flex items-center space-x-4">
                  <Link
                    to="/profile"
                    className="flex items-center space-x-2 border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl transition-all duration-300 group"
                  >
                    <FaUser className="text-primary group-hover:scale-110 transition-transform duration-300" />
                    <span className="text-sm font-medium text-white">
                      {user?.username}
                    </span>
                  </Link>
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="flex items-center space-x-2 border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl text-sm font-medium text-white hover:text-primary transition-all duration-300"
                  >
                    <FaSignOutAlt />
                    <span>Logout</span>
                  </button>
                </div>
              ) : (
                <div className="flex items-center space-x-3">
                  <Link
                    to="/login"
                    className="border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl text-sm font-medium text-white hover:text-primary transition-all duration-300"
                  >
                    Login
                  </Link>
                  <Button asChild className="rounded-xl">
                    <Link to="/register">Register</Link>
                  </Button>
                </div>
              )}

              {/* Mobile Menu Button */}
              <button
                type="button"
                onClick={toggleMobileMenu}
                className="md:hidden border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 p-2 rounded-lg text-white hover:text-primary transition-all duration-300"
              >
                {isMobileMenuOpen ? <FaTimes /> : <FaBars />}
              </button>
            </div>
          </div>
        </div>

        {/* Bottom Tier - Navigation */}
        <nav className="border-t border-white/10">
          <div className="container mx-auto px-4">
            <div className="hidden md:flex items-center justify-between py-2">
              <div className="flex items-center space-x-1">
                <NavLink to="/builder" icon={<BsTools />}>
                  Builder
                </NavLink>
                <NavLink to="/build-lists" icon={<GiRaceCar />}>
                  Build Lists
                </NavLink>
                <NavLink to="/parts" icon={<FaCogs />}>
                  Parts Catalog
                </NavLink>
                <NavLink to="/search" icon={<FaSearch />}>
                  Search
                </NavLink>
              </div>
              <div className="flex items-center space-x-1">
                <ExternalNavLink
                  href={CHROME_EXTENSION_STORE_URL}
                  icon={<FaChrome />}
                >
                  Get Extension
                </ExternalNavLink>
                <NavLink to="/bug-report" icon={<FaBug />}>
                  Report a Bug
                </NavLink>
                <NavLink to="/support" icon={<FaCoffee />}>
                  Support Us
                </NavLink>
                {user?.is_admin && (
                  <NavLink to="/admin" icon={<FaCogs />}>
                    Admin
                  </NavLink>
                )}
              </div>
            </div>
          </div>
        </nav>

        {/* Mobile Menu */}
        {isMobileMenuOpen && (
          <div className="md:hidden animate-slideInUp">
            <div className="border border-white/10 bg-white/5 backdrop-blur-xl mx-4 mb-4 rounded-xl">
              <div className="p-4 space-y-3">
                {isAuthenticated ? (
                  <div className="space-y-3">
                    <Link
                      to="/profile"
                      className="flex items-center space-x-2 text-white hover:text-primary transition-colors duration-300"
                      onClick={() => setIsMobileMenuOpen(false)}
                    >
                      <FaUser className="text-primary" />
                      <span className="font-medium">{user?.username}</span>
                    </Link>
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="w-full flex items-center justify-center space-x-2 border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl text-sm font-medium text-white"
                    >
                      <FaSignOutAlt />
                      <span>Logout</span>
                    </button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <Link
                      to="/login"
                      className="block w-full text-center border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl text-sm font-medium text-white"
                      onClick={() => setIsMobileMenuOpen(false)}
                    >
                      Login
                    </Link>
                    <Button asChild className="w-full rounded-xl">
                      <Link
                        to="/register"
                        onClick={() => setIsMobileMenuOpen(false)}
                      >
                        Register
                      </Link>
                    </Button>
                  </div>
                )}

                <div className="border-t border-white/10 pt-3 space-y-2">
                  <MobileNavLink
                    to="/builder"
                    icon={<BsTools />}
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    Builder
                  </MobileNavLink>
                  <MobileNavLink
                    to="/parts"
                    icon={<FaCogs />}
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    Parts Catalog
                  </MobileNavLink>

                  <MobileNavLink
                    to="/build-lists"
                    icon={<GiRaceCar />}
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    Build Lists
                  </MobileNavLink>
                  <MobileNavLink
                    to="/search"
                    icon={<FaSearch />}
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    Search
                  </MobileNavLink>
                  <MobileExternalNavLink
                    href={CHROME_EXTENSION_STORE_URL}
                    icon={<FaChrome />}
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    Get Extension
                  </MobileExternalNavLink>
                  <MobileNavLink
                    to="/bug-report"
                    icon={<FaBug />}
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    Report a Bug
                  </MobileNavLink>
                  <MobileNavLink
                    to="/support"
                    icon={<FaCoffee />}
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    Support Us
                  </MobileNavLink>
                  {user?.is_admin && (
                    <MobileNavLink
                      to="/admin"
                      icon={<FaCogs />}
                      onClick={() => setIsMobileMenuOpen(false)}
                    >
                      Admin
                    </MobileNavLink>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}

// Desktop Navigation Link Component
function NavLink({
  to,
  icon,
  children,
}: {
  to: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Link
      to={to}
      className="flex items-center space-x-2 px-4 py-3 text-sm font-medium text-foreground hover:text-white hover:bg-white/5 rounded-xl transition-all duration-300 group"
    >
      <span className="group-hover:scale-110 transition-transform duration-300">
        {icon}
      </span>
      <span>{children}</span>
    </Link>
  );
}

// Mobile Navigation Link Component
function MobileNavLink({
  to,
  icon,
  children,
  onClick,
}: {
  to: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className="flex items-center space-x-3 px-3 py-2 text-sm font-medium text-foreground hover:text-white hover:bg-white/5 rounded-lg transition-all duration-300"
    >
      <span className="text-lg">{icon}</span>
      <span>{children}</span>
    </Link>
  );
}

// Desktop External Link Component (opens in new tab)
function ExternalNavLink({
  href,
  icon,
  children,
}: {
  href: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center space-x-2 px-4 py-3 text-sm font-medium text-foreground hover:text-white hover:bg-white/5 rounded-xl transition-all duration-300 group"
    >
      <span className="group-hover:scale-110 transition-transform duration-300">
        {icon}
      </span>
      <span>{children}</span>
    </a>
  );
}

// Mobile External Link Component (opens in new tab)
function MobileExternalNavLink({
  href,
  icon,
  children,
  onClick,
}: {
  href: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onClick={onClick}
      className="flex items-center space-x-3 px-3 py-2 text-sm font-medium text-foreground hover:text-white hover:bg-white/5 rounded-lg transition-all duration-300"
    >
      <span className="text-lg">{icon}</span>
      <span>{children}</span>
    </a>
  );
}

export default Header;
