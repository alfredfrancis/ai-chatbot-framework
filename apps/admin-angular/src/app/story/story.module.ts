import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { StoryComponent } from './story.component';
import { StoryService } from './story.service';
import { RouterModule } from '@angular/router';
import { StoryRoutes } from './story.routing';
import {MatButtonModule, MatCheckboxModule, MatCardModule, MatIconModule, MatToolbarModule} from '@angular/material';
import { StoriesComponent } from './stories.component';
import { HttpModule } from '@angular/http';
import { TrainComponent } from './train.component';

@NgModule({
  imports: [
    CommonModule,
    HttpModule,
    RouterModule.forRoot(StoryRoutes),
    MatButtonModule, MatCheckboxModule, MatCardModule, MatIconModule, MatToolbarModule
  ],
  declarations: [StoryComponent, StoriesComponent, TrainComponent],
  exports: [StoryComponent, StoriesComponent, TrainComponent],
  entryComponents: [StoryComponent, StoriesComponent, TrainComponent],
  providers: [
    StoryService
  ],
})
export class StoryModule { }
