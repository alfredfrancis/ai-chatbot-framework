
import { StoryComponent } from './story.component';
import { StoriesComponent } from './stories.component';

export const StoryRoutes = [
    { component: StoriesComponent, name: 'Story', path: 'stories' },
    { component: StoryComponent, name: 'StoryNew', path: 'story/new' },
    { component: StoryComponent, name: 'StoryEdit', path: 'story/:id' }
];
