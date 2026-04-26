import React from 'react';
import { Link } from 'react-router-dom';
import type { UserRead } from '../../types/Api';
import { Card } from '../ui/card';

interface UserCardProps {
  user: UserRead;
}

const UserCard: React.FC<UserCardProps> = ({ user }) => {
  return (
    <Link to={`/user/${user.id}`} className="block hover:no-underline h-full">
      <Card className="flex flex-col h-full hover:border-indigo-500 border-2 border-transparent transition-colors">
        <div className="flex items-center gap-4">
          {user.image_urls?.[0] ? (
            <img
              src={user.image_urls[0]}
              alt={user.username}
              className="w-16 h-16 rounded-full object-cover"
            />
          ) : (
            <div className="w-16 h-16 rounded-full bg-gray-700 flex items-center justify-center">
              <span className="text-2xl text-gray-400">
                {user.username.charAt(0).toUpperCase()}
              </span>
            </div>
          )}
          <div className="flex-grow">
            <h3 className="text-lg font-semibold text-indigo-400 mb-1">
              {user.username}
            </h3>
            <p className="text-sm text-gray-400">{user.email}</p>
          </div>
        </div>
      </Card>
    </Link>
  );
};

export default UserCard;
