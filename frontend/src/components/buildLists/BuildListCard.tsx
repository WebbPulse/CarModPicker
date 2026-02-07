import React from 'react';
import { Link } from 'react-router-dom';
import { FaArrowUp } from 'react-icons/fa';
import Card from '../common/Card';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';
import type { BuildListRead, BuildListReadWithVotes } from '../../types/Api';

interface BuildListCardProps {
  buildList: BuildListRead | BuildListReadWithVotes;
}

function hasVoteData(
  bl: BuildListRead | BuildListReadWithVotes
): bl is BuildListReadWithVotes {
  return 'total_votes' in bl && typeof (bl as BuildListReadWithVotes).total_votes === 'number';
}

const BuildListCard: React.FC<BuildListCardProps> = ({ buildList }) => {
  const showVoteBadge = hasVoteData(buildList);
  const totalVotes = showVoteBadge ? buildList.total_votes : 0;

  return (
    <Link
      to={`/build-lists/${buildList.id}`}
      className="block hover:no-underline"
    >
      <Card className="h-full hover:border-primary-500 border-2 border-transparent transition-all duration-300 group">
        <div className="relative mb-4">
          <ImageWithPlaceholder
            srcUrl={buildList.image_url ?? null}
            altText={buildList.name}
            imageClassName="w-full h-48 object-cover rounded-lg group-hover:scale-105 transition-transform duration-300"
            containerClassName="w-full h-48"
            fallbackText="No image"
          />
          {showVoteBadge && (
            <div className="absolute top-3 right-3 flex items-center gap-1 bg-black/60 backdrop-blur-sm px-2 py-1 rounded-lg">
              <FaArrowUp className="text-primary-400 text-xs" />
              <span className="text-xs font-semibold text-white">
                {totalVotes} votes
              </span>
            </div>
          )}
        </div>
        <h3 className="text-xl font-semibold text-white mb-2 group-hover:text-primary-400 transition-colors">
          {buildList.name}
        </h3>
        {buildList.description && (
          <p className="text-sm text-neutral-400 line-clamp-2">
            {buildList.description}
          </p>
        )}
      </Card>
    </Link>
  );
};

export default BuildListCard;
