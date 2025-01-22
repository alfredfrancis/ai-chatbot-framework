import React from 'react';

interface IntegrationTileProps {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  status: boolean;
  onClick: () => void;
}

const IntegrationTile: React.FC<IntegrationTileProps> = ({
  name,
  description,
  icon,
  status,
  onClick,
}) => {
  return (
    <div
      onClick={onClick}
      className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow cursor-pointer"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-4">
          <div className="text-gray-600">
            {icon}
          </div>
          <div>
            <h3 className="text-lg font-medium text-gray-800">{name}</h3>
            <p className="text-sm text-gray-600">{description}</p>
          </div>
        </div>
        <span className={`text-sm px-2.5 py-0.5 rounded-full ${
          status === true 
            ? 'bg-green-100 text-green-800'
            : 'bg-gray-100 text-gray-800'
        }`}>
          {status ? 'Active' : 'Inactive'}
        </span>
      </div>
    </div>
  );
};

export default IntegrationTile; 