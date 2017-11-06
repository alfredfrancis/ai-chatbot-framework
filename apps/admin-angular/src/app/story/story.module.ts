import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { StoryComponent } from './story.component';
import { StoryService } from './story.service';
import { RouterModule } from '@angular/router';
import { StoryRoutes } from './story.routing';
import {MatButtonModule, MatCheckboxModule, MatCardModule, MatIconModule} from '@angular/material';
import { StoriesComponent } from './stories.component';
import { HttpModule } from '@angular/http';

@NgModule({
  imports: [
    CommonModule,
    HttpModule,
    RouterModule.forRoot(StoryRoutes),
    MatButtonModule, MatCheckboxModule, MatCardModule, MatIconModule,
  ],
  declarations: [StoryComponent, StoriesComponent],
  exports: [StoryComponent, StoriesComponent],
  entryComponents: [StoryComponent, StoriesComponent],
  providers: [
    StoryService
  ],
})
export class StoryModule { }
